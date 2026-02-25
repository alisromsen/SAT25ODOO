# -*- coding: utf-8 -*-
from odoo import models,fields, api
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from datetime import datetime


class DescargaXDiaWizard(models.TransientModel):
    _name ='descarga.x.dia.wizard'
    _description = 'DescargaXDiaWizard'

    start_date = fields.Date("Fecha de inicio")
    end_date = fields.Date("Fecha Final")
    descripcion = fields.Char(string='Descripción')

    def create_request_download_xml(self):
        # Agregando datos a estado de cuenta
        tipo_cfdi = 'Provedores'
        vals_verificador = {
            'start_date': self.start_date,
            'end_date': self.end_date,
            'tipo_cfdi': tipo_cfdi,
            'descripcion': self.descripcion,
            'origin': 'Por Rango de Fecha',
            'state': 'en_proceso',
        }
        crea_verificador = self.env['bei.verifica.descarga'].sudo().with_context().create(vals_verificador)
        action = crea_verificador.env["ir.actions.actions"]._for_xml_id(
            "bei_sat_ws.bei_verifica_descarga_action")
        form_view = [(crea_verificador.env.ref('bei_sat_ws.bei_verifica_descarga_form_view').id, 'form')]
        action['views'] = form_view
        action['res_id'] = crea_verificador.id
        # start_date = self.start_date.strftime(DEFAULT_SERVER_DATE_FORMAT)
        # start_date += ' 00:00:00'
        # start_date = datetime.strptime(start_date,DEFAULT_SERVER_DATETIME_FORMAT)
        #
        # end_date = self.end_date.strftime(DEFAULT_SERVER_DATE_FORMAT)
        # end_date += ' 23:59:59'
        # end_date = datetime.strptime(end_date,DEFAULT_SERVER_DATETIME_FORMAT)
        # self.env.company.sudo().download_cfdi_invoices_api(start_date, end_date)
        return action
