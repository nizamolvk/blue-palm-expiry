from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class BluePalmExpiryItem(models.Model):
    _name = "blue_palm.expiry.item"
    _description = "Expiry Item"
    _order = "expiry_date, id"

    name = fields.Char(required=True)
    item_type = fields.Selection(
        selection=[
            ("licence", "Licence"),
            ("insurance", "Insurance"),
            ("vehicle", "Vehicle"),
            ("permit", "Permit"),
            ("warranty", "Warranty"),
            ("subscription", "Subscription"),
            ("other", "Other"),
        ],
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    responsible_id = fields.Many2one("res.users")
    expiry_date = fields.Date()
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
    )
    annual_cost = fields.Monetary(currency_field="currency_id")
    external_ref = fields.Char(string="External reference")
    status = fields.Selection(
        selection=[
            ("valid", "Valid"),
            ("expiring", "Expiring within 30 days"),
            ("expired", "Expired"),
            ("no_date", "No date"),
        ],
        compute="_compute_status",
        store=True,
        index=True,
    )

    @api.model
    def _get_today(self):
        raw = self.env["ir.config_parameter"].sudo().get_param("blue_palm_expiry.today")
        if raw:
            return fields.Date.to_date(raw)
        return fields.Date.context_today(self)

    @api.depends("expiry_date")
    def _compute_status(self):
        today = self._get_today()
        limit = today + timedelta(days=30)
        for item in self:
            if not item.expiry_date:
                item.status = "no_date"
            elif item.expiry_date < today:
                item.status = "expired"
            elif item.expiry_date <= limit:
                item.status = "expiring"
            else:
                item.status = "valid"

    @api.constrains("annual_cost")
    def _check_annual_cost(self):
        for item in self:
            if item.annual_cost < 0:
                raise ValidationError("Annual cost cannot be negative.")

    @api.model
    def _cron_update_status(self):
        records = self.search([])
        records.modified(["expiry_date"])
        records.flush_recordset(["status"])
