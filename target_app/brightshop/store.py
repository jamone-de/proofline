"""In-memory data store. Everything the app knows lives in one Store."""


class Store:
    def __init__(self):
        self.products = {}
        self.customers = {}
        self.orders = {}
        self.invoices = {}
        self.stock = {}

    def add_product(self, product, stock=0):
        self.products[product.sku] = product
        self.stock[product.sku] = stock

    def add_customer(self, customer):
        self.customers[customer.id] = customer

    def add_order(self, order):
        self.orders[order.id] = order

    def add_invoice(self, invoice):
        self.invoices[invoice.number] = invoice

    def next_order_id(self):
        return max(self.orders, default=1000) + 1

    def orders_for_customer(self, customer_id):
        return [o for o in self.orders.values() if o.customer_id == customer_id]

    def invoices_for_order(self, order_id):
        return [i for i in self.invoices.values() if i.order_id == order_id]

    def invoices_for_customer(self, customer_id):
        return [i for i in self.invoices.values() if i.customer_id == customer_id]
