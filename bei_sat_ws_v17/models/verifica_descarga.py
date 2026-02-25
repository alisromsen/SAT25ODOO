# coding: utf-8

from odoo import api, fields, models, _
from odoo.tools.misc import format_date
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from datetime import datetime
import logging
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class BeiVerificaSolicitudDescarga(models.Model):
    _name = "bei.verifica.descarga"
    _description = "Verificación de Solicitud de Descarga de XML"

    #------------------------------------METODO CREATE--------------------------------------------------------------
    def create(self, vals):
        company_id = vals.get('company_id', self.default_get(['company_id'])['company_id'])
        # seleccion de la moneda de la compañia
        self_comp = self.with_company(company_id)
        if vals.get('name', 'New') == 'New':
            _logger.info(" NEW...............")

            start_date = fields.Date.to_date(vals.get('start_date'))
            end_date = fields.Date.to_date(vals.get('end_date'))
            if start_date and end_date:
                diferencia = (end_date - start_date).days
                if diferencia < 0:
                    raise ValidationError("La fecha final no puede ser menor que la fecha de inicio.")
                if diferencia >= 31:
                    raise ValidationError(f"Hay {diferencia} dias entre el rango de fechas seleccionadas y este NO debe ser mayor a 30 dias.")
            seq_date = None
            if 'date_order' in vals:
                _logger.info(" DATE EN VALS...")
                seq_date = fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(vals['date_order']))
            vals['name'] = self_comp.env['ir.sequence'].next_by_code('bei.verifica.descarga',
                                                                     sequence_date=seq_date) or '/'

        res = super(BeiVerificaSolicitudDescarga, self_comp).create(vals)
        return res

    #datos por defecto---------------------------------------------------------------------------------
    name = fields.Char(string='Referencia', required=True, copy=False, readonly=True, index=True, default='New')
    date_order = fields.Datetime('Creación', required=True, index=True, copy=False, default=fields.Datetime.now)
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, default=lambda self: self.env.company.id)
    user_id = fields.Many2one('res.users', string='Usuario', index=True, default=lambda self: self.env.user, check_company=True)
    #--------------------------------------------------------------------------------------------------
    last_cfdi_fetch_date = fields.Datetime("Última sincronización")
    descripcion = fields.Char(string='Descripcion')
    cod_estado_solicitud = fields.Char(string='Cod. Solicitud')
    start_date = fields.Date("Fecha de inicio")
    end_date = fields.Date("Fecha Final")
    tipo_cfdi = fields.Char(string='Tipo de CFDI')
    idsolicitud = fields.Char(string='Solicitud')
    origin = fields.Char(string='Origen')
    respuesta_api = fields.Text(string='Respuesta WS API')
    estado_solicitud = fields.Selection([
        ('0', 'Token invalido'),
        ('1', 'Aceptada'),
        ('2', 'En proceso'),
        ('3', 'Terminada'),
        ('4', 'Error'),
        ('5', 'Rechazada'),
        ('6', 'Vencida'),
        ('inactiva', 'Inactiva'),
    ], string='Estado de Solicitud', readonly=True, copy=False)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('en_proceso', 'En proceso'),
        ('done', 'Realizada'),
        ('cancel', 'Cancelada'),
        ('inactiva', 'Inactiva'),
    ], string='Status', readonly=True, copy=False, default='draft')
    descarga_realizada = fields.Boolean("Descarga Realizada")

    def action_desactivar(self):
        self.state = 'inactiva'
        return True
    # ###################################### AUTOMATIC ###############################################################
    @api.model
    def _cron_ejecutar_verificacion(self):
        _logger.info("CRON------------VERIFICADOR---------------------")

        return self._ejecuta_verificacion(automatic=True)

    def _ejecuta_verificacion(self, automatic=False):
        _logger.info("--ejecutando VERIFICACION---")
        if automatic:
            today = fields.Date.today()
            _logger.info(today)
            verifica_solicitud = self.env['bei.verifica.descarga'].search(
                [('state', '=', 'en_proceso'), ('descarga_realizada', '=', False)], order='date_order asc')
            _logger.info(verifica_solicitud)
            if verifica_solicitud:
                for so in verifica_solicitud:
                    _logger.info(so.name)
                    _logger.info(" *********INIT*******")
                    so.download_cfdi_invoices_btw_two_dates()
                    _logger.info(" *********FIN*******")
        return True

    def download_cfdi_invoices_btw_two_dates(self):
        # Realiza el proceso de verificacion si hay un ID_solicitud ..si no realiza la solicitud
        _logger.info("Iniciando Proceso de revision de solicitud**************")
        _logger.info(self.company_id.name)
        verifica = False
        if not self.idsolicitud:
            start_date = self.start_date.strftime(DEFAULT_SERVER_DATE_FORMAT)
            start_date += ' 00:00:00'
            start_date = datetime.strptime(start_date, DEFAULT_SERVER_DATETIME_FORMAT)

            end_date = self.end_date.strftime(DEFAULT_SERVER_DATE_FORMAT)
            end_date += ' 23:59:59'
            end_date = datetime.strptime(end_date, DEFAULT_SERVER_DATETIME_FORMAT)

            # hacer solicitud
            _logger.info("H A C I E N D O ------------ S O L I C I T U D")
            api_request = self.company_id.sudo().api_init_request_suppliers(start_date, end_date)
            solicitud = api_request['solicitud']
            if solicitud:
                self.idsolicitud = solicitud['id_solicitud']
        if self.idsolicitud:
            _logger.info("SI HAY ID DE SOLICITUD")
            verifica = self.company_id.sudo().api_save_download(self.idsolicitud, self.id)
        else:
            self.respuesta_api = 'No hay ID de Solicitud'

        if verifica:
            _logger.info("SE HA VERIFICADO")
            _logger.info(verifica)
            estado_sol = verifica['estado_solicitud']
            realizado = verifica['realizado']
            cod_estado_solicitud = verifica['cod_estado_solicitud']
            self.estado_solicitud = str(estado_sol)
            self.cod_estado_solicitud = str(cod_estado_solicitud)
            self.respuesta_api = verifica['respuesta']
            if realizado:
                _logger.info("REALIZADO CON EXITO!!")
                self.descarga_realizada = True
                self.state = 'done'
        else:
            self.respuesta_api = 'No se puedo realizar la verificación'
        self.last_cfdi_fetch_date = datetime.now()
        _logger.info("FIN Proceso-------------------------")
        return True

