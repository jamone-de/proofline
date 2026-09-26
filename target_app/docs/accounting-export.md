# Accounting export

Month end export for the tax accountant.

Run the sales report with `reporting.build_sales_report(...)` and then
`reporting.export_report(report, "csv")`. The accountant used to ask for an XML
variant, produced by `reporting.export_xml_report`. The XML export is no longer
requested but was never removed.

Invoices for customers without e-mail used to be sent with `fax_gateway.send_invoice_fax`.
That workflow ended in 2023.
