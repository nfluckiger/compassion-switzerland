# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2018 Compassion CH (http://www.compassion.ch)
#    Releasing children from poverty in Jesus' name
#    @author: Nathan Fluckiger <nathan.fluckiger@hotmail.ch>
#
#    The licence is in the file __manifest__.py
#
##############################################################################
from odoo import models, fields, api, tools
from odoo.tools.config import config
import httplib
import base64
import urllib


class SmsSender(models.TransientModel):

    _name = 'sms.sender'

    text = fields.Text()
    partner_id = fields.Many2one(comodel_name='res.partner',
                                 compute='_compute_partner')

    @api.model
    @api.depends('text')
    def _compute_partner(self):
        self.partner_id = self.env.context.get('partner_id', False)
        if not self.partner_id:
            print("Une erreur est survenue ")

    @api.multi
    def send_sms(self):
        if not self.partner_id.mobile:
            return False

        headers = {}
        username = config.get('939_username')
        password = config.get('939_password')

        request_server = httplib.HTTPConnection(
            'blue.smsbox.ch', 10020, timeout=10)

        auth = base64.encodestring('%s:%s' % (username,
                                              password)).replace('\n', '')

        headers['Authorization'] = 'Basic ' + auth
        for sms in self:
            request = [
                ('receiver', self.partner_id.mobile.replace(u'\xa0', u'')),
                ('service', 'compassion'),
                ('cost', 0),
                ('text', self.text)
            ]
            print(urllib.urlencode(request))
            request_server.request('GET', '/Blue/sms/rest/user/websend?'
                                   + urllib.urlencode(request), headers=headers)
            reponse = request_server.getresponse()
            print(reponse.read())
            sms.partner_id.message_post(body=sms.text,
                                        subject='Spontaneous SMS',
                                        partner_ids=sms.partner_id,
                                        type='comment')
        return True
