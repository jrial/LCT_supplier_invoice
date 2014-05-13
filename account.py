# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import fields, osv, orm
from openerp.tools.translate import _
from openerp import netsvc
import csv
import base64
from cStringIO import StringIO
import datetime

class res_partner(osv.osv):
    _name = "res.partner"
    _inherit = "res.partner"

    _columns = {
        'is_cmms_supplier': fields.boolean(string="CMMS Supplier"),
    }

class account_invoice_line(osv.osv):

    _name = "account.invoice.line"
    _inherit = "account.invoice.line"

    _columns = {
        'parent_type': fields.related('invoice_id', 'type', type="char", store=True),
        'cost_purpose': fields.char('Cost Purpose'),
        'object_nr': fields.char('Object Nr'),
        'object_description': fields.char('Object Description'),
        'project_nr': fields.char('Project Nr'),
        'project_description': fields.char('Project Description'),
        'wo_nr': fields.char('WO Nr'),
        'wo_description': fields.char('WO Description'),
        'part_nr': fields.char('Part Nr'),
        'part_description': fields.char('Part Description'),
        'po_nr': fields.char('PO Nr'),
        'po_line': fields.char('PO Line'),
        'asset': fields.char('Asset', size=80),
        'deviation': fields.char('Deviation', size=80),
        'state': fields.related('invoice_id', 'state', type="char", string="Status"),
    }


class account_invoice(osv.osv):

    _name = "account.invoice"
    _inherit = "account.invoice"

    _columns = {
        'invoice_line': fields.one2many('account.invoice.line', 'invoice_id', 'Invoice Lines', readonly=True, states={'draft':[('readonly',False)], 'synchronized':[('readonly',False)]}),
        'approved': fields.char(string='Approved'),
        'cost_purpose': fields.char(string="Cost Purpose"),
        'synchronized': fields.boolean(string="Synchronized"),
        'state': fields.selection([
            ('draft','Draft'),
            ('proforma','Pro-forma'),
            ('proforma2','Pro-forma'),
            ('sent','Sent to CMMS'),
            ('synchronized', 'Synchronized'),
            ('open','Validated'),
            ('paid','Paid'),
            ('cancel','Cancelled'),
            ],'Status', select=True, readonly=True, track_visibility='onchange',
            help=' * The \'Draft\' status is used when a user is encoding a new and unconfirmed Invoice. \
            \n* The \'Pro-forma\' when invoice is in Pro-forma status,invoice does not have an invoice number. \
            \n* The \'Open\' status is used when user create invoice,a invoice number is generated.Its in open status till user does not pay invoice. \
            \n* The \'Paid\' status is set automatically when the invoice is paid. Its related journal entries may or may not be reconciled. \
            \n* The \'Cancelled\' status is used when user cancel invoice.'),
        'internal_number': fields.char('Invoice Number', size=32, help="Unique number of the invoice, computed automatically when the invoice is created."),
        'supplier_invoice_number': fields.char('Supplier Invoice Number', size=64, help="The reference of this invoice as provided by the supplier.", required=True, states={'draft':[('readonly',False)]}),
        'po_number': fields.char('PO number', size=32),
        'is_cmms_supplier': fields.related('partner_id', 'is_cmms_supplier', type='boolean'),
        'template': fields.boolean(string="Template"),
    }
    _defaults = {
        'synchronized': False,
    }

    def onchange_supplier_number(self, cr, uid, ids, supplier_invoice_number, context=None):
        n = self.search(cr, uid, [
            ('supplier_invoice_number', '=', supplier_invoice_number),
        ], count=True)
        if n > 0:
            warning = {
                'title': _('Supplier Invoice Number'),
                'message': _('This Supplier Invoice Number is already used!')
            }
            return {'warning': warning}
        return {}

    def action_cancel_draft(self, cr, uid, ids, *args):
        self.write(cr, uid, ids, {'state':'draft', 'synchronized': False})
        wf_service = netsvc.LocalService("workflow")
        for inv_id in ids:
            wf_service.trg_delete(uid, 'account.invoice', inv_id, cr)
            wf_service.trg_create(uid, 'account.invoice', inv_id, cr)
        return True

    def val_synch(self, cr, uid, ids, context=None):
        wf_service = netsvc.LocalService("workflow")
        for index in ids:
            wf_service.trg_validate(uid, "account.invoice", int(index), "invoice_cancel", cr)
        self.action_cancel_draft(cr, uid, ids, [])
        self.write(cr, uid, ids, {'synchronized': True}, context=context)
        for index in ids:
            wf_service.trg_validate(uid, "account.invoice", int(index), "invoice_open", cr)
        return True

    def write(self, cr, uid, ids, vals, context=None):
        if 'synchronized' in vals and vals['synchronized']:
            to_synch_ids = self.search(cr, uid, [('id', 'in', ids), ('synchronized', '=', False), ('state', '=', 'sent')], context=context)
            to_update_ids = self.search(cr, uid, [('id', 'in', ids), ('state', '=', 'synchronized')], context=context)

            invoice_line_reg = self.pool.get('account.invoice.line')
            invoice_tax_reg = self.pool.get('account.invoice.tax')
            move_reg = self.pool.get('account.move')
            wf_service = netsvc.LocalService("workflow")

            if to_synch_ids:
                invoice_line_ids = invoice_line_reg.search(cr, uid, [('invoice_id', 'in', to_synch_ids)], context=context)
                invoice_line_reg.unlink(cr, uid, invoice_line_ids, context=context)
            to_synch_ids.extend(to_update_ids)
            invoice_tax_ids = invoice_tax_reg.search(cr, uid, [('invoice_id', 'in', to_synch_ids)], context=context)
            invoice_tax_reg.unlink(cr, uid, invoice_tax_ids, context=context)
            self.write(cr, uid, to_synch_ids, {'state': 'draft'}, context=context)
            super(account_invoice, self).write(cr, uid, to_synch_ids, vals, context=context)
            self.write(cr, uid, to_synch_ids, {'state': 'synchronized'}, context=context)

            return True
        else:
            return super(account_invoice, self).write(cr, uid, ids, vals, context=context)

    def create(self, cr, uid, vals, context=None):
        vals.update({'synchronized': False})
        return super(account_invoice, self).create(cr, uid, vals, context=context)

    def _prepare_refund(self, cr, uid, invoice, date=None, period_id=None, description=None, journal_id=None, context=None):
        res = super(account_invoice, self)._prepare_refund(cr, uid, invoice, date=date, period_id=period_id, description=description, journal_id=journal_id, context=context)
        res['supplier_invoice_number'] = 'supplier_invoice_number' in invoice and invoice['supplier_invoice_number'] or False
        return res

class account_voucher(osv.osv):

    _name = 'account.voucher'
    _inherit = 'account.voucher'

    def proforma_voucher(self, cr, uid, ids, context=None):
        for voucher in self.browse(cr, uid, ids, context=context):
            for elmt in voucher.line_dr_ids:
                if elmt.move_line_id:
                    invoice = elmt.move_line_id.invoice
                    if invoice and invoice.type and invoice.type == 'in_invoice':
                        if not 'state' in invoice or not invoice.state or not invoice.state == 'open' or not 'approved' in invoice or (not invoice.approved == 'A' and not invoice.approved == 'a'):
                            raise osv.except_osv(_('Error!'),_("The invoice must be approved before payment."))
        return super(account_voucher, self).proforma_voucher(cr, uid, ids, context=context)

    def button_proforma_voucher(self, cr, uid, ids, context=None):
        context = context or {}
        if context.get('active_ids'):
            invoice = self.pool.get('account.invoice').browse(cr, uid, context.get('active_ids')[0], context=context)
            if invoice.type == 'in_invoice':
                if not 'approved' in invoice or not invoice.approved == 'A':
                    raise osv.except_osv(_('Error!'),_("The invoice must be approved before payment."))
        return super(account_voucher, self).button_proforma_voucher(cr, uid, ids, context=context)

    _columns = {
        'template': fields.boolean(string="Template"),
    }


class account_export(osv.osv_memory):

    _name = "account.export"

    def export(self, cr, uid, ids, context=None):
        invoice_reg = self.pool.get("account.invoice")
        wiz = self.browse(cr, uid, ids, context=context)[0]
        wf_service = netsvc.LocalService("workflow")

        if len(wiz.invoice_ids)==0:
            return True
        invoice_reg = self.pool.get('account.invoice')
        for inv in wiz.invoice_ids:
            invoice_reg.action_date_assign(cr, uid, [inv.id])
            invoice_reg.action_move_create(cr, uid, [inv.id])
            invoice_reg.action_number(cr, uid, [inv.id])
            invoice_reg.write(cr, uid, [inv.id], {'state': 'sent'}, context=context)

        # the export
        fields = ['id', 'partner_id', 'currency_id', 'date_invoice', 'date_due', 'invoice_line/price_subtotal', 'invoice_line/invoice_line_tax_id', 'amount_total', 'internal_number', 'po_number']
        rows = invoice_reg.export_data(cr, uid, [inv.id for inv in wiz.invoice_ids], fields, context=context)
        fp = StringIO()
        writer = csv.writer(fp, quoting=csv.QUOTE_ALL, delimiter=';')

        writer.writerow([name.encode('utf-8') for name in fields])

        for data in rows['datas']:
            row = []
            for d in data:
                if isinstance(d, basestring):
                    d = d.replace('\n',' ').replace('\t',' ')
                    try:
                        d = d.encode('utf-8')
                    except UnicodeError:
                        pass
                if d is False: d = None
                row.append(d)
            writer.writerow(row)

        fp.seek(0)
        data = fp.read()
        fp.close()

        encode_text = base64.encodestring(data)
        self.write(cr, uid, ids, {
            'file': encode_text,
            'state': 'saved',
            'datas_fname': 'supplier_invoice_' + str(datetime.datetime.now().strftime('%Y-%m-%d_%H:%M:%S')) + '.csv'
            }, context=context)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Export Invoice to CMMS',
            'res_model': 'account.export',
            'res_id': ids[0],
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
            'context': context,
        }

    def _get_invoices(self, cr, uid, context=None):
        return self.pool.get("account.invoice").search(cr, uid, [('type', '=', 'in_invoice'), ('state', '=', 'draft'), ('synchronized', '=', False)], context=context)

    _columns = {
        'invoice_ids': fields.many2many('account.invoice', string="Export", domain=[('type', '=', 'in_invoice'), ('state', '=', 'draft'), ('synchronized', '=', False)]),
        'datas_fname': fields.char("File Name", 128),
        'file': fields.binary('File', readonly=True),
        'state': fields.selection([
            ('draft','Draft'),
            ('saved', 'Saved')], readonly=True),
    }
    _defaults = {
        'invoice_ids': _get_invoices,
        'state': 'draft',
    }