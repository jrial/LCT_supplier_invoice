openerp.LCT_supplier_invoice = function (instance) {

	var _lt = instance.web._lt;

	instance.web.DataImport.include({
		opts: [
            {name: 'encoding', label: _lt("Encoding:"), value: 'utf-8'},
            {name: 'separator', label: _lt("Separator:"), value: ';'},
            {name: 'quoting', label: _lt("Quoting:"), value: '"'}
        ],
	});
};