class DomainError(Exception):
    def __init__(self, **fields):
        super().__init__(fields.get("message", type(self).__name__))
        self.fields = fields
