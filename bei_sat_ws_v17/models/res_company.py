# -*- coding: utf-8 -*-
import base64
import io

import subprocess
import tempfile
import time
import zipfile
from datetime import timedelta, datetime
from dateutil.relativedelta import relativedelta
from functools import partial
from lxml import etree, objectify
from odoo import models, api, fields, _
from odoo.exceptions import UserError
from .sat_api_import import SAT
from .special_dict import CaselessDictionary
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from time import sleep
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import logging
_logger = logging.getLogger(__name__)

TYPE_CFDI22_TO_CFDI33 = {
    'ingreso': 'I',
    'egreso': 'E',
    'traslado': 'T',
    'nomina': 'N',
    'pago': 'P',
}

ERROR_TYPE = [(0, 'Token invalido.'), (1, 'Aceptada'), (2, 'En proceso'), (3, 'Terminada'), (4, 'Error'),
              (5, 'Rechazada'), (6, 'Vencida')]


class BeiResCompany(models.Model):
    _inherit = 'res.company'

    last_cfdi_fetch_date = fields.Datetime("Última sincronización")
    l10n_mx_esignature_ids = fields.Many2many('l10n.mx.esignature.certificate', string='Certificado FIEL')
    solo_documentos_de_proveedor = fields.Boolean("Solo documentos de proveedor", default=True)

    def api_init_request_suppliers(self, start_date, end_Date):
        _logger.info(self.name)
        _logger.info("Entrando a company metodo INICIO DE SOLICITUD")
        _logger.info(start_date)
        _logger.info(end_Date)

        date_from = start_date
        date_to = end_Date
        esignature_ids = self.l10n_mx_esignature_ids
        esignature = esignature_ids.with_user(self.env.user).get_valid_certificate()
        #_logger.info(esignature.holder)
        if not esignature:
            raise UserError(_("No valido Firma no Encontrada."))

        sat_obj = SAT(esignature.content, esignature.key, esignature.password)
        _logger.info("GENERANDO TOKEN******-----ARC")
        token = sat_obj.soap_generate_token(sat_obj.certificate, sat_obj.private_key)

        #_logger.info(" **** S E G U I M O S C O N    EL  T O K E N........")
        _logger.info(token)
        _logger.info(" **** -------------------------------------------........")
        # Recibidos -- Supplier
        #tipo_comprobante = 'E'  tipo_comprobante=tipo_comprobante
        solicitud = sat_obj.soap_request_download(token=token, date_from=date_from, date_to=date_to, rfc_receptor=True)
        _logger.info("SOLICITUD !! REALIZADO-------------------------")
        _logger.info(solicitud)
        return {'esignature': esignature, 'sat_obj': sat_obj, 'solicitud': solicitud, 'token': token}

    def api_save_download(self, solicitud, secuencia_id):
        res = self.save_downloaded_content_verificador(solicitud, secuencia_id, False)
        self.last_cfdi_fetch_date = datetime.now()

        return res

    ##### Download by API
    # def download_cfdi_invoices_api(self, start_date=False, end_Date=False):
    #     # date_from = datetime.date(2023, 4, 1)
    #     date_from = self.last_cfdi_fetch_date if self.last_cfdi_fetch_date else fields.Datetime.now()
    #     # date_to = datetime.date(2024, 2, 1)
    #     date_to = fields.Datetime.now() + timedelta(days=1)
    #     if start_date:
    #         date_from = start_date
    #     if end_Date:
    #         date_to = end_Date
    #     esignature_ids = self.l10n_mx_esignature_ids
    #     esignature = esignature_ids.with_user(self.env.user).get_valid_certificate()
    #     if not esignature:
    #         raise UserError(_("No valido Firma no Encontrada."))
    #
    #     sat_obj = SAT(esignature.content, esignature.key, esignature.password)
    #     token = sat_obj.soap_generate_token(sat_obj.certificate, sat_obj.private_key)
    #
    #     # Recibidos -- Supplier
    #     solicitud = sat_obj.soap_request_download(token=token, date_from=date_from, date_to=date_to, rfc_receptor=True)
    #     _logger.info("SOLICITUD DE DESCARGA!! REALIZADO-------------------------")
    #     _logger.info(solicitud)
    #     res = self.save_downloaded_content(esignature, sat_obj, solicitud, False)
    #     # if not res:
    #     #     time.sleep(2)
    #     #     # Emitidos -- customer
    #     #     solicitud = sat_obj.soap_request_download(token=token, date_from=date_from, date_to=date_to,
    #     #                                               rfc_emisor=True)
    #     #     self.save_downloaded_content(esignature, sat_obj, solicitud, False)
    #     #     _logger.info("realizado- despues de sleep--------")
    #     #     _logger.info(solicitud)
    #
    #     self.last_cfdi_fetch_date = datetime.now()
    #     title = _("¡REALIZADO!")
    #     message = _(
    #         "Se ha realizado el proceso")
    #
    #     res = {
    #         'type': 'ir.actions.client',
    #         'tag': 'display_notification',
    #         'params': {
    #             'title': title,
    #             'message': message,
    #             'sticky': False, }
    #     }
    #     return res

    # def save_downloaded_content(self, esignature, sat_obj, solicitud, customer_documents):
    #     _logger.info("save_downloaded_content *************")
    #     content = []
    #     for _ in range(10):
    #         token = sat_obj.soap_generate_token(sat_obj.certificate, sat_obj.private_key)
    #         #VERIFICAR
    #         #Verificación: pregunta al SAT si ya tiene disponible la solicitud.
    #         _logger.info("VERIFICACION DE PAQUETE **************************************")
    #         verificacion = sat_obj.soap_verify_package(esignature.holder_vat, solicitud['id_solicitud'], token)
    #         #_logger.info(f'\n >>> SOLICITUD: {verificacion}')
    #         estado_solicitud = int(verificacion['estado_solicitud'])
    #         _logger.info("**** status solicitud ******")
    #         _logger.info(estado_solicitud)
    #         # 0, Token invalido.
    #         # 1, Aceptada
    #         # 2, En proceso
    #         # 3, Terminada
    #         # 4, Error
    #         # 5, Rechazada
    #         # 6, Vencida
    #         if estado_solicitud <= 2:
    #             _logger.info("**** status menor a 2 esperar 60 seg ...................")
    #             # Si el estado de solicitud esta Aceptado o en proceso el programa espera
    #             # 60 segundos y vuelve a tratar de verificar
    #             time.sleep(60)
    #             continue
    #         elif estado_solicitud >= 4:
    #             _logger.info("****status mayor igual a 4  envia mensaje ERROR TYPE...................")
    #             message = f"{ERROR_TYPE[estado_solicitud]} - {verificacion['mensaje']}"
    #             #_logger.info(f"\n >>> {message}")
    #             self.env['bus.bus']._sendone(self.env.user.partner_id, 'simple_notification',
    #                                          {'title': "Error", 'message': message, 'sticky': False, 'warning': True})
    #             break
    #         else:
    #             _logger.info("****status  3 ****************!!!!!!")
    #             # Si el estatus es 3 se trata de descargar los paquetes
    #             for paquete in verificacion['paquetes']:
    #                 descarga = sat_obj.soap_download_package(esignature.holder_vat, paquete, token)
    #                 #_logger.info(descarga)
    #                 content.append(descarga['paquete_b64'])
    #             break
    #     if not content:
    #         _logger.info("8888888888888 No hay XML  888888888")
    #         return True
    #
    #     attachment_obj = self.env['ir.attachment']
    #     invoice_obj = self.env['account.move']
    #     payment_obj = self.env['account.payment']
    #     NSMAP = {
    #         'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
    #         'cfdi': 'http://www.sat.gob.mx/cfd/3',
    #         'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital',
    #         'pago10': 'http://www.sat.gob.mx/Pagos',
    #     }
    #
    #     # Supplier
    #     attach_obj = self.env['ir.attachment'].sudo()
    #     _logger.info(" ZIPFILE ......CONTENT.......")
    #     with zipfile.ZipFile(io.BytesIO(base64.b64decode(content[0]))) as z:
    #         for attachment_name in z.namelist():
    #             _logger.info(attachment_name)
    #             with z.open(attachment_name) as att_xml:
    #                 xml_content = att_xml.read()
    #                 _logger.info("leyendo XML content-----------------------------------------------------------------")
    #                 cfdi_etree = self._check_objectify_xml(base64.b64encode(xml_content))
    #                 tfd_node = self._get_et_cfdi_node(cfdi_etree)
    #                 uuid = tfd_node.get('UUID').upper().strip() if tfd_node.get('UUID') else 'No firmado'
    #                 attachments = attach_obj.search([
    #                     ('cfdi_uuid', '=', uuid),
    #                     ('company_id', '=', self.id)])
    #                 if attachments:
    #                     continue
    #                 try:
    #                     values = dict(etree.fromstring(xml_content).items())
    #                 except:
    #                     continue
    #                 if b'xmlns:schemaLocation' in xml_content:
    #                     xml_content = xml_content.replace(b'xmlns:schemaLocation', b'xsi:schemaLocation')
    #                 try:
    #                     tree = etree.fromstring(xml_content)
    #                     _logger.info(
    #                         "leyendo XML tree-----------------------------------------------------------------")
    #                     _logger.info(tree)
    #
    #                 except Exception as e:
    #                     self.env['bus.bus']._sendone(self.env.user.partner_id, 'simple_notification',
    #                                          {'title': "Error", 'message': "No pudo leer un XML descargado", 'sticky': False, 'warning': True})
    #                     _logger.error('error etree.fromstring: ' + str(e))
    #                     continue
    #                 try:
    #                     ns = tree.nsmap
    #                     ns.update({'re': 'http://exslt.org/regular-expressions'})
    #                 except Exception:
    #                     ns = {'re': 'http://exslt.org/regular-expressions'}
    #
    #                 xml_content = base64.b64encode(xml_content)
    #                 _logger.info(" TENGO xml_content")
    #
    #                 ns_url = ns.get('cfdi')
    #                 root_tag = 'Comprobante'
    #                 if ns_url:
    #                     root_tag = '{' + ns_url + '}Comprobante'
    #                 # Validation to only admit CFDI
    #                 if tree.tag != root_tag:
    #                     # Invalid invoice file.
    #                     continue
    #
    #                 # receptor_elements = tree.xpath('//cfdi:Emisor', namespaces=tree.nsmap)
    #                 if customer_documents:
    #                     _logger.info("customer_documents NO DEBERIA ENTRAR AQUI")
    #                     try:
    #                         emisor_elements = tree.xpath("//*[re:test(local-name(), 'Receptor','i')]", namespaces=ns)
    #                     except Exception:
    #                         _logger.info("No encontró al receptor")
    #                     r_rfc, r_name, r_folio = '', '', ''
    #                     if emisor_elements:
    #                         attrib_dict = CaselessDictionary(dict(emisor_elements[0].attrib))
    #                         r_rfc = attrib_dict.get('rfc')  # emisor_elements[0].get(attrib_dict.get('rfc'))
    #                         r_name = attrib_dict.get('nombre')  # emisor_elements[0].get(attrib_dict.get('nombre'))
    #                 else:
    #                     _logger.info("Receptor YO RECIBO---------")
    #                     try:
    #                         receptor_elements = tree.xpath("//*[re:test(local-name(), 'Emisor','i')]", namespaces=ns)
    #                     except Exception:
    #                         receptor_elements = False
    #                         _logger.info("No encontró al emisor")
    #                     r_rfc, r_name, r_folio = '', '', ''
    #                     if receptor_elements:
    #                         attrib_dict = CaselessDictionary(dict(receptor_elements[0].attrib))
    #                         r_rfc = attrib_dict.get('rfc')  # receptor_elements[0].get(attrib_dict.get('rfc'))
    #                         r_name = attrib_dict.get('nombre')  # receptor_elements[0].get(attrib_dict.get('nombre'))
    #
    #                 r_folio = tree.get("Folio")  # receptor_elements[0].get(attrib_dict.get('nombre'))
    #
    #                 cfdi_version = tree.get("Version", '4.0')
    #                 _logger.info(" **** VERSION *****")
    #                 _logger.info(cfdi_version)
    #                 if cfdi_version == '4.0':
    #
    #                     NSMAP.update(
    #                         {'cfdi': 'http://www.sat.gob.mx/cfd/4', 'pago20': 'http://www.sat.gob.mx/Pagos20', })
    #                 else:
    #
    #                     NSMAP.update(
    #                         {'cfdi': 'http://www.sat.gob.mx/cfd/3', 'pago10': 'http://www.sat.gob.mx/Pagos', })
    #
    #                 cfdi_type = tree.get("TipoDeComprobante", 'I')
    #                 _logger.info(" **** TipoDeComprobante *****")
    #                 _logger.info(cfdi_type)
    #                 if cfdi_type not in ['I', 'E', 'P', 'N', 'T']:
    #                     cfdi_type = 'I'
    #                 if not customer_documents:
    #                     _logger.info(" **** not documentos del cliente ALERTA NO DEBERIA DE*****")
    #                     cfdi_type = 'S' + cfdi_type
    #
    #                 monto_total = 0
    #                 if cfdi_type in ['SP', 'P']:
    #                     complemento = tree.find('cfdi:Complemento', NSMAP)
    #                     if cfdi_version == '4.0':
    #                        pagos = complemento.find('pago20:Pagos', NSMAP)
    #                        pago = pagos.find('pago20:Totales', NSMAP)
    #                        monto_total = pago.attrib['MontoTotalPagos']
    #                     else:
    #                        pagos = complemento.find('pago10:Pagos', NSMAP)
    #                        try:
    #                           pago = pagos.find('pago10:Pago',NSMAP)
    #                           monto_total = pago.attrib['Monto']
    #                        except Exception as e:
    #                           for payment in pagos.find('pago10:Pago',NSMAP):
    #                               monto_total += float(payment.attrib['Monto'])
    #                 else:
    #                     monto_total = tree.get('Total', 0.0)
    #
    #                 filename = uuid + '.xml'  # values.get('receptor','')[:10]+'_'+values.get('rfc_receptor')
    #                 vals = dict(
    #                     name=filename,
    #                     store_fname=filename,
    #                     type='binary',
    #                     datas=xml_content,
    #                     cfdi_uuid=uuid,
    #                     company_id=self.id,
    #                     cfdi_type=cfdi_type,
    #                     rfc_tercero=r_rfc,
    #                     nombre_tercero=r_name,
    #                     serie_folio=r_folio,
    #                     cfdi_total=monto_total,
    #                 )
    #                 vals.update({'date_cfdi': tree.get('Fecha')})  # .strftime(DEFAULT_SERVER_DATE_FORMAT)})
    #                 if customer_documents:
    #                     _logger.info(" //////////customer_documents ///////////////")
    #                     if cfdi_type == 'P':
    #                         for uu in [uuid, uuid.lower(), uuid.upper()]:
    #                             payment_exist = payment_obj.search([('l10n_mx_edi_cfdi_uuid_cusom', '=', uu), ('company_id','=',self.id)], limit=1)
    #                             if payment_exist:
    #                                 vals.update({'creado_en_odoo': True, 'payment_ids': [(6, 0, payment_exist.ids)]})
    #                                 break
    #                     elif cfdi_type == 'E':
    #                         for uu in [uuid, uuid.lower(), uuid.upper()]:
    #                             invoice_exist = invoice_obj.search([('l10n_mx_edi_cfdi_uuid_cusom', '=', uu), ('company_id','=',self.id)], limit=1)
    #                             if invoice_exist:
    #                                 vals.update({'creado_en_odoo': True, 'invoice_ids': [(6, 0, invoice_exist.ids)]})
    #                                 break
    #                     else:
    #                         for uu in [uuid, uuid.lower(), uuid.upper()]:
    #                             invoice_exist = invoice_obj.search([('l10n_mx_edi_cfdi_uuid_cusom', '=', uu), ('company_id','=',self.id)], limit=1)
    #                             if invoice_exist:
    #                                 vals.update({'creado_en_odoo': True, 'invoice_ids': [(6, 0, invoice_exist.ids)]})
    #                                 break
    #                 else:
    #                     if cfdi_type == 'SP':
    #                         for uu in [uuid, uuid.lower(), uuid.upper()]:
    #                             payment_exist = payment_obj.search(
    #                                 [('l10n_mx_edi_cfdi_uuid_cusom', '=', uu), ('payment_type', '=', 'outbound'), ('company_id','=',self.id)], limit=1)
    #                             if payment_exist:
    #                                 vals.update({'creado_en_odoo': True, 'payment_ids': [(6, 0, payment_exist.ids)]})
    #                                 break
    #                     elif cfdi_type == 'SE':
    #                         for uu in [uuid, uuid.lower(), uuid.upper()]:
    #                             invoice_exist = invoice_obj.search(
    #                                 [('l10n_mx_edi_cfdi_uuid_cusom', '=', uu), ('move_type', '=', 'in_refund'), ('company_id','=',self.id)], limit=1)
    #                             if invoice_exist:
    #                                 vals.update({'creado_en_odoo': True, 'invoice_ids': [(6, 0, invoice_exist.ids)]})
    #                                 break
    #                     else:
    #                         _logger.info("NO ES SE ni documento cliente")
    #                         for uu in [uuid, uuid.lower(), uuid.upper()]:
    #                             invoice_exist = invoice_obj.search(
    #                                 [('l10n_mx_edi_cfdi_uuid_cusom', '=', uu), ('move_type', '=', 'in_invoice'), ('company_id','=',self.id)], limit=1)
    #                             if invoice_exist:
    #                                 vals.update({'creado_en_odoo': True, 'invoice_ids': [(6, 0, invoice_exist.ids)]})
    #                                 break
    #                 attachment_obj.create(vals)

    def save_downloaded_content_verificador(self, solicitud, secuencia_id, customer_documents):
        _logger.info("save_downloaded_content verificador *************")
        realizado = False
        numero_cfdis = 0
        paquete = None
        sol_sat_id = self.env['bei.verifica.descarga'].browse(secuencia_id)
        _logger.info("Solicitud ID")
        _logger.info(sol_sat_id)
        _logger.info(solicitud)
        esignature_ids = self.l10n_mx_esignature_ids
        esignature = esignature_ids.with_user(self.env.user).get_valid_certificate()
        sat_obj = SAT(esignature.content, esignature.key, esignature.password)
        token = sat_obj.soap_generate_token(sat_obj.certificate, sat_obj.private_key)
        _logger.info(token)
        content = []
        for _ in range(2):
            _logger.info("---------pregunta al SAT si ya tiene disponible la solicitud------------------")
            verificacion = sat_obj.soap_verify_package(esignature.holder_vat, solicitud, token)
            _logger.info("PAQUETE **************************************")
            _logger.info(verificacion)
            numero_cfdis = verificacion['numero_cfdis']
            respuesta = verificacion['mensaje']
            estado_solicitud = int(verificacion['estado_solicitud'])
            cod_estado_solicitud = int(verificacion['codigo_estado_solicitud'])
            # 0, Token invalido.
            # 1, Aceptada
            # 2, En proceso
            # 3, Terminada
            # 4, Error
            # 5, Rechazada
            # 6, Vencida
            if estado_solicitud <= 2:
                _logger.info("**** status menor a 2 esperar 10 seg ...................")
                _logger.info(estado_solicitud)
                # Si el estado de solicitud esta Aceptado o en proceso el programa espera
                # 30 segundos y vuelve a tratar de verificar
                time.sleep(10)
                if estado_solicitud == 2:
                    respuesta = 'En proceso'
                elif estado_solicitud == 1:
                    respuesta = 'Aceptado'
                else:
                    respuesta = 'Token invalido'
                continue
            elif estado_solicitud >= 4:
                _logger.info("****status mayor igual a 4  envia mensaje ERROR TYPE...................")
                message = f"{ERROR_TYPE[estado_solicitud]} - {verificacion['mensaje']}"
                _logger.info(f"\n >>> {message}")
                if estado_solicitud == 4:
                    respuesta = 'Error'
                elif estado_solicitud == 5:
                    respuesta = 'Rechazada'
                else:
                    respuesta = 'Vencida'
                break

            else:
                _logger.info("****status  3 ****************!!!!!!")
                # Si el estatus es 3 se trata de descargar los paquetes
                for paquete in verificacion['paquetes']:
                    descarga = sat_obj.soap_download_package(esignature.holder_vat, paquete, token)
                    _logger.info(descarga)
                    content.append(descarga['paquete_b64'])
                respuesta = respuesta + ' DD:' + descarga['mensaje']
                paquete = descarga['paquete_b64']
                break

        _logger.info(" *******respuesta ")
        _logger.info(respuesta)



        if not content or paquete is None:
            _logger.info("8888888888888 No hay XML  888888888------------------------------------------------------------------------------------------------------------------------------------")
            return {'estado_solicitud': str(estado_solicitud), 'cod_estado_solicitud': str(cod_estado_solicitud), 'realizado': realizado, 'respuesta': respuesta, 'numero_cfdis': numero_cfdis}

        _logger.info(" HAY CONTENT ")
        #_logger.info(content)
        attachment_obj = self.env['ir.attachment']
        invoice_obj = self.env['account.move']
        payment_obj = self.env['account.payment']
        NSMAP = {
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
            'cfdi': 'http://www.sat.gob.mx/cfd/3',
            'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital',
            'pago10': 'http://www.sat.gob.mx/Pagos',
        }

        # Supplier
        attach_obj = self.env['ir.attachment'].sudo()
        _logger.info(" ZIPFILE ......CONTENT.......")
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(content[0]))) as z:
            for attachment_name in z.namelist():
                _logger.info(attachment_name)
                with z.open(attachment_name) as att_xml:
                    xml_content = att_xml.read()
                    _logger.info("leyendo XML content-----------------------------------------------------------------")
                    cfdi_etree = self._check_objectify_xml(base64.b64encode(xml_content))
                    tfd_node = self._get_et_cfdi_node(cfdi_etree)
                    uuid = tfd_node.get('UUID').upper().strip() if tfd_node.get('UUID') else 'No firmado'

                    attachments = attach_obj.search([
                        ('cfdi_uuid', '=', uuid),
                        ('company_id', '=', sol_sat_id.company_id.id)])    #self.id
                    if attachments:
                        continue
                    try:
                        values = dict(etree.fromstring(xml_content).items())
                    except:
                        continue
                    if b'xmlns:schemaLocation' in xml_content:
                        xml_content = xml_content.replace(b'xmlns:schemaLocation', b'xsi:schemaLocation')
                    try:
                        tree = etree.fromstring(xml_content)
                        _logger.info(
                            "leyendo XML tree-----------------------------------------------------------------")
                        _logger.info(tree)

                    except Exception as e:
                        self.env['bus.bus']._sendone(self.env.user.partner_id, 'simple_notification',
                                                     {'title': "Error", 'message': "No pudo leer un XML descargado", 'sticky': False, 'warning': True})
                        _logger.error('error etree.fromstring: ' + str(e))
                        continue
                    try:
                        ns = tree.nsmap
                        ns.update({'re': 'http://exslt.org/regular-expressions'})
                    except Exception:
                        ns = {'re': 'http://exslt.org/regular-expressions'}

                    xml_content = base64.b64encode(xml_content)
                    _logger.info(" TENGO xml_content")

                    ns_url = ns.get('cfdi')
                    root_tag = 'Comprobante'
                    if ns_url:
                        root_tag = '{' + ns_url + '}Comprobante'
                    # Validation to only admit CFDI
                    if tree.tag != root_tag:
                        # Invalid invoice file.
                        continue

                    # receptor_elements = tree.xpath('//cfdi:Emisor', namespaces=tree.nsmap)
                    if customer_documents:
                        continue
                    else:
                        _logger.info("Receptor YO RECIBO---------")
                        try:
                            receptor_elements = tree.xpath("//*[re:test(local-name(), 'Emisor','i')]", namespaces=ns)
                        except Exception:
                            receptor_elements = False
                            _logger.info("No encontró al emisor")
                        r_rfc, r_name, r_folio = '', '', ''
                        if receptor_elements:
                            attrib_dict = CaselessDictionary(dict(receptor_elements[0].attrib))
                            r_rfc = attrib_dict.get('rfc')  # receptor_elements[0].get(attrib_dict.get('rfc'))
                            r_name = attrib_dict.get('nombre')  # receptor_elements[0].get(attrib_dict.get('nombre'))

                    r_folio = tree.get("Folio")  # receptor_elements[0].get(attrib_dict.get('nombre'))

                    cfdi_version = tree.get("Version", '4.0')
                    _logger.info(" **** VERSION *****")
                    _logger.info(cfdi_version)
                    if cfdi_version == '4.0':
                        NSMAP.update(
                            {'cfdi': 'http://www.sat.gob.mx/cfd/4', 'pago20': 'http://www.sat.gob.mx/Pagos20', })
                    else:

                        NSMAP.update(
                            {'cfdi': 'http://www.sat.gob.mx/cfd/3', 'pago10': 'http://www.sat.gob.mx/Pagos', })

                    cfdi_type = tree.get("TipoDeComprobante", 'I')
                    _logger.info(" **** TipoDeComprobante *****")
                    _logger.info(cfdi_type)
                    prb = tree.get("TipoDeComprobante")
                    _logger.info(cfdi_type)
                    # if cfdi_type not in ['I', 'E', 'P', 'N', 'T']:
                    #     cfdi_type = 'I'
                    #     _logger.info(" **** cfdi_type no en IEPNT--->I")
                    # if not customer_documents:
                    #     _logger.info(" **** no documentos del cliente ---> S")
                    cfdi_type = 'S' + cfdi_type
                    monto_total = 0
                    if cfdi_type in ['SP', 'P']:
                        continue
                    else:
                        monto_total = tree.get('Total', 0.0)

                    filename = uuid + '.xml'  # values.get('receptor','')[:10]+'_'+values.get('rfc_receptor')

                    vals = dict(
                        name=filename,
                        store_fname=filename,
                        type='binary',
                        datas=xml_content,
                        cfdi_uuid=uuid,
                        company_id=sol_sat_id.company_id.id,             #self.id, lambda self: self.env.company
                        cfdi_type=cfdi_type,
                        rfc_tercero=r_rfc,
                        nombre_tercero=r_name,
                        serie_folio=r_folio,
                        cfdi_total=monto_total,
                    )
                    vals.update({'date_cfdi': tree.get('Fecha')})  # .strftime(DEFAULT_SERVER_DATE_FORMAT)})
                    vals.update({'solicitud_sat_id': sol_sat_id.id})

                    if cfdi_type == 'SP':
                        continue
                    elif cfdi_type == 'SE':
                        continue
                    else:
                        _logger.info("Es factura proveedor")
                        _logger.info(cfdi_type)
                        for uu in [uuid, uuid.lower(), uuid.upper()]:
                            invoice_exist = invoice_obj.search(
                                [('l10n_mx_edi_cfdi_uuid_cusom', '=', uu), ('move_type', '=', 'in_invoice'),
                                 ('company_id', '=', sol_sat_id.company_id.id)], limit=1)
                            if invoice_exist:
                                vals.update({'creado_en_odoo': True, 'invoice_ids': [(6, 0, invoice_exist.ids)]})
                                break
                    adjuntos = attachment_obj.create(vals)
                    if adjuntos:
                        realizado = True
        return {'estado_solicitud': str(estado_solicitud), 'cod_estado_solicitud': str(cod_estado_solicitud),
                'realizado': realizado, 'respuesta': respuesta, 'numero_cfdis': numero_cfdis}

    def _xml2capitalize(self, xml):
        """Receive 1 lxml etree object and change all attrib to Capitalize.
        """

        def recursive_lxml(element):
            for attrib, value in element.attrib.items():
                new_attrib = "%s%s" % (attrib[0].upper(), attrib[1:])
                element.attrib.update({new_attrib: value})

            for child in element.getchildren():
                child = recursive_lxml(child)
            return element

        return recursive_lxml(xml)

    def _convert_cfdi32_to_cfdi33(self, cfdi_etree):
        """Convert a xml from cfdi32 to cfdi33
        :param xml: The xml 32 in lxml.objectify object
        :return: A xml 33 in lxml.objectify object
        """
        if cfdi_etree.get('version', None) not in ('3.2', '3.0', '2.2', '2.0') or \
                cfdi_etree.get('Version', None) == '3.3':
            return cfdi_etree
        cfdi_etree = self._xml2capitalize(cfdi_etree)
        cfdi_etree.attrib.update({
            'TipoDeComprobante': TYPE_CFDI22_TO_CFDI33[
                cfdi_etree.attrib['tipoDeComprobante']],
            # 'Version': '3.2',
            # By default creates Payment Complement since that the imported
            # moves are most imported for this propose if it is not the case
            # then modified manually from odoo.
            'MetodoPago': 'PPD',
        })
        return cfdi_etree

    def _check_objectify_xml(self, xml64, partner_create=False, cfdi_check=False):
        try:
            _logger.info("------- _check_objectify_xml ---------")
            if isinstance(xml64, bytes):
                xml64 = xml64.decode()
            xml_str = base64.b64decode(xml64.replace('data:text/xml;base64,', ''))
            xml_str = xml_str.replace(b'xmlns:schemaLocation', b'xsi:schemaLocation')
            cfdi_etree = objectify.fromstring(xml_str)
        except (etree.XMLSyntaxError) as e:
            _logger.error(str(e))
            return {}
        except (AttributeError, SyntaxError, ValueError) as e:
            _logger.error(str(e))
            return False
        cfdi_etree = self._convert_cfdi32_to_cfdi33(cfdi_etree)
        if partner_create == True:
            partner_exist = self.env['res.partner'].search([
                ('vat', '=', cfdi_etree.Emisor.get('Rfc'))], limit=1, order='id asc')
            if not partner_exist:
                partner_exist = self.env['res.partner'].sudo().create({
                    'name': cfdi_etree.Emisor.get('Nombre', ''),
                    'vat': cfdi_etree.Emisor.get('Rfc', ''),
                    'country_id': self.env.ref('base.mx').id,
                })
                msg = _('This partner was created when CFDI import process was being '
                        'executed. Please verify that the datas of partner are '
                        'correct.')
                partner_exist.message_post(subject=_('Info'), body=msg)

        # TODO implement a better way to check if datas is a CFDI
        if cfdi_check:
            return True if (hasattr(cfdi_etree, 'Complemento') and
                            cfdi_etree.tag in ('{http://www.sat.gob.mx/cfd/3}Comprobante')) else False

        return cfdi_etree

    def _get_et_cfdi_node(self, cfdi_etree, attribute='tfd:TimbreFiscalDigital[1]',
                          namespaces={'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'}):
        ''' Helper to extract relevant data from CFDI 3.3 nodes.
        By default this method will retrieve tfd, Adjust parameters for other nodes
        :param cfdi_etree:  The cfdi etree object.
        :param attribute:   tfd.
        :param namespaces:  tfd.
        :return:            A python dictionary.
        '''
        if not hasattr(cfdi_etree, 'Complemento'):
            _logger.info("------- _get_et_cfdi_node ---------")
            return False
        node = cfdi_etree.Complemento.xpath(attribute, namespaces=namespaces)
        return node[0] if node else False

