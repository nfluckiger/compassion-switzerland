# -*- encoding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2016 Compassion CH (http://www.compassion.ch)
#    Releasing children from poverty in Jesus' name
#    @author: Emanuel Cino <ecino@compassion.ch>
#
#    The licence is in the file __openerp__.py
#
##############################################################################
import base64
from collections import OrderedDict
from datetime import datetime

from dateutil.relativedelta import relativedelta
from pyPdf import PdfFileWriter, PdfFileReader
from io import BytesIO

from openerp import api, models, _, fields
from openerp.exceptions import MissingError

from openerp.addons.sponsorship_compassion.models.product import GIFT_NAMES


class PartnerCommunication(models.Model):
    _inherit = 'partner.communication.job'

    def get_dossier_full_attachments(self):
        return self._get_new_dossier_attachments()

    def get_dossier_payer_attachments(self):
        return self._get_new_dossier_attachments(correspondence=False)

    def get_dossier_correspondent_attachments(self):
        return self._get_new_dossier_attachments(payment=False)

    def get_correspondence_attachments(self):
        """
        Include PDF of letters only if less than 3 letters are sent,
        or if the send_mode is to print the letters.
        :return: dict {attachment_name: [report_name, pdf_data]}
        """
        self.ensure_one()
        attachments = dict()
        # Report is used for print configuration
        report = 'report_compassion.b2s_letter'
        letters = self.get_objects()
        if not letters.get_multi_mode() or self.send_mode == 'physical':
            for letter in self.get_objects():
                try:
                    attachments[letter.letter_image.name] = [
                        report, self._convert_pdf(letter.letter_image.datas)]
                except MissingError:
                    self.send_mode = False
                    self.auto_send = False
                    self.message_post(
                        "The letter image is missing!", "Missing letter")
                    continue
        else:
            # Attach directly a zip in the letters
            letters.attach_zip()
        return attachments

    def get_sub_form(self):
        """
        Attach sub sponsorship form
        :return: dict {attachment_name: [report_name, pdf_data]}
        """
        self.ensure_one()
        attachments = dict()
        report = 'report_compassion.sub_proposal'
        report_obj = self.env['report']
        attachments[_('sub child form.pdf')] = [
            report,
            base64.b64encode(report_obj.get_pdf(self.partner_id, report))
        ]
        return attachments

    def get_birthday_bvr(self):
        """
        Attach birthday gift slip with background for sending by e-mail
        :return: dict {attachment_name: [report_name, pdf_data]}
        """
        self.ensure_one()
        attachments = dict()
        background = self.send_mode and 'physical' not in self.send_mode
        sponsorships = self.get_objects().filtered(
            lambda s: not s.birthday_paid)
        if sponsorships:
            birthday_gift = self.env['product.product'].with_context(
                lang='en_US').search([('name', '=', GIFT_NAMES[0])])
            attachments = sponsorships.get_bvr_gift_attachment(
                birthday_gift, background)
        return attachments

    def get_graduation_bvr(self):
        """
        Attach graduation gift slip with background for sending by e-mail
        :return: dict {attachment_name: [report_name, pdf_data]}
        """
        self.ensure_one()
        background = self.send_mode and 'physical' not in self.send_mode
        sponsorships = self.get_objects()
        graduation = self.env['product.product'].with_context(
            lang='en_US').search([('name', '=', GIFT_NAMES[4])])
        return sponsorships.get_bvr_gift_attachment(
            graduation, background)

    def get_reminder_bvr(self):
        """
        Attach sponsorship due payment slip with background for sending by
        e-mail.
        :return: dict {attachment_name: [report_name, pdf_data]}
        """
        self.ensure_one()
        sponsorships = self.get_objects()

        # Verify big due periods
        if len(sponsorships.mapped('due_invoice_ids.period_id')) > 3:
            self.need_call = True

        payment_term = sponsorships.with_context(lang='en_US').mapped(
            'payment_term_id.name')[0]
        # LSV-DD Waiting reminders special case
        if 'Waiting Reminder' in self.config_id.name and (
                'LSV' in payment_term or 'Postfinance' in payment_term):
            if self.partner_id.bank_ids:
                # We received the bank info but withdrawal didn't work.
                # Mark to call in order to verify the situation.
                self.need_call = True
            else:
                # Don't put payment slip if we just wait the authorization form
                return dict()

        # Put product sponsorship to print the payment slip for physical print.
        if self.send_mode and 'physical' in self.send_mode:
            self.product_id = self.env[
                'product.product'].with_context(lang='en_US').search([
                    ('name', '=', 'Sponsorship')], limit=1)
            return dict()

        # In other cases, attach the payment slip.
        report_name = 'report_compassion.bvr_due'
        return {
            _('sponsorship due.pdf'): [
                report_name,
                base64.b64encode(self.env['report'].get_pdf(
                    sponsorships, report_name,
                    data={'background': True, 'doc_ids': sponsorships.ids}
                ))
            ]
        }

    def get_label_attachment(self, sponsorships=False):
        """
        Attach sponsorship labels.
        :return: dict {attachment_name: [report_name, pdf_data]}
        """
        self.ensure_one()
        if not sponsorships:
            sponsorships = self.env['recurring.contract']
            children = self.get_objects()
            for child in children:
                sponsorships += child.sponsorship_ids[0]
        attachments = dict()
        label_print = self.env['label.print'].search([
            ('name', '=', 'Sponsorship Label')], limit=1)
        label_brand = self.env['label.brand'].search([
            ('brand_name', '=', 'Herma A4')], limit=1)
        label_format = self.env['label.config'].search([
            ('name', '=', '4455 SuperPrint WeiB')], limit=1)
        label_wizard = self.env['label.print.wizard'].with_context({
            'active_ids': sponsorships.ids,
            'active_model': 'recurring.contract',
            'label_print': label_print.id,
        }).create({
            'brand_id': label_brand.id,
            'name': label_format.id,
            'number_of_labels': 33
        })
        label_data = label_wizard.get_report_data()
        label_context = self.env.context.copy()
        label_context.update(label_data['form'])
        label_context.update({
            'active_model': 'label.print.wizard',
            'active_id': label_wizard.id,
            'active_ids': label_wizard.ids,
            'label_print': label_print.id
        })
        report_name = 'label.report_label'
        attachments[_('sponsorship labels.pdf')] = [
            report_name,
            base64.b64encode(
                self.env['report'].with_context(label_context).get_pdf(
                    label_wizard, report_name, data=label_data))
        ]
        return attachments

    def get_child_picture_attachment(self):
        """
        Attach child pictures to communication. It directly attach them
        to the communication if sent by e-mail and therefore does
        return an empty dictionary.
        :return: dict {}
        """
        self.ensure_one()
        res = dict()
        if self.send_mode and 'physical' not in self.send_mode:
            # Prepare attachments in case the communication is sent by e-mail
            children = self.get_objects()
            attachments = self.env['ir.attachment']
            for child in children:
                pic = child.pictures_ids[0]
                attachment = self.env['ir.attachment'].search([
                    ('res_model', '=', 'compassion.child.pictures'),
                    ('res_id', '=', pic.id),
                    ('datas_fname', 'like', 'Fullshot')
                ])
                attachments += attachment.copy({
                    'name': child.local_id + ' ' + child.last_photo_date +
                    '.jpg'})
            self.with_context(no_print=True).ir_attachment_ids = attachments
        else:
            self.ir_attachment_ids = False
        return res

    @api.multi
    def send(self):
        """
        - Mark B2S correspondence as read when printed.
        - Postpone no money holds when reminders sent.
        :return: True
        """
        super(PartnerCommunication, self).send()
        b2s_printed = self.filtered(
            lambda c: c.config_id.model == 'correspondence' and
            c.send_mode == 'physical' and c.state == 'done')
        if b2s_printed:
            letters = b2s_printed.get_objects()
            if letters:
                letters.write({'letter_delivered': True})

        # No money extension
        no_money_1 = self.env.ref('partner_communication_switzerland.'
                                  'sponsorship_waiting_reminder_1')
        no_money_2 = self.env.ref('partner_communication_switzerland.'
                                  'sponsorship_waiting_reminder_2')
        settings = self.env['availability.management.settings']
        first_extension = settings.get_param('no_money_hold_duration')
        second_extension = settings.get_param('no_money_hold_extension')
        now = datetime.now()
        for communication in self:
            extension = False
            if communication.config_id == no_money_1:
                # Add 7 days because reminders are created 7 days in advance
                extension = now + relativedelta(days=first_extension+7)
            elif communication.config_id == no_money_2:
                extension = now + relativedelta(days=second_extension+7)
            if extension:
                holds = communication.get_objects().mapped('child_id.hold_id')
                holds.write({
                    'expiration_date': fields.Datetime.to_string(extension)
                })
            return True

    def _get_new_dossier_attachments(self, correspondence=True, payment=True):
        """
        Returns pdfs for the New Dossier Communication, including:
        - Sponsorship payment slips (if payment is True)
        - Small Childpack
        - Sponsorship labels (if correspondence is True)
        :return: dict {attachment_name: [report_name, pdf_data]}
        """
        self.ensure_one()
        attachments = OrderedDict()
        report_obj = self.env['report']

        sponsorships = self.get_objects()
        # Include all active sponsorships for Permanent Order
        if 'Permanent Order' in sponsorships.with_context(
                lang='en_US').mapped('payment_term_id.name'):
            sponsorships += sponsorships.mapped(
                'group_id.contract_ids').filtered(
                lambda s: s.state == 'active')

        # Payment slips
        if payment:
            report_name = 'report_compassion.3bvr_sponsorship'
            attachments.update({
                _('sponsorship payment slips.pdf'): [
                    report_name,
                    base64.b64encode(report_obj.get_pdf(
                        sponsorships, report_name,
                        data={'doc_ids': sponsorships.ids}
                    ))
                ]
            })

        # Gifts
        sponsorships = self.get_objects()
        report_name = 'report_compassion.3bvr_gift_sponsorship'
        attachments.update({
            _('sponsorship gifts.pdf'): [
                report_name,
                base64.b64encode(report_obj.get_pdf(
                    sponsorships, report_name,
                    data={'doc_ids': sponsorships.ids}
                ))
            ]
        })

        # Childpack
        children = sponsorships.mapped('child_id')
        report_name = 'report_compassion.childpack_small'
        attachments[_('child dossier.pdf')] = [
            report_name,
            base64.b64encode(report_obj.get_pdf(children, report_name))
        ]

        # Labels
        if correspondence:
            attachments.update(self.get_label_attachment(sponsorships))

        return attachments

    def _convert_pdf(self, pdf_data):
        """
        Converts all pages of PDF in A4 format if communication is
        printed.
        :param pdf_data: binary data of original pdf
        :return: binary data of converted pdf
        """
        if self.send_mode != 'physical':
            return pdf_data

        pdf = PdfFileReader(BytesIO(base64.b64decode(pdf_data)))
        convert = PdfFileWriter()
        a4_width = 594.48
        a4_height = 844.32  # A4 units in PyPDF
        for i in xrange(0, pdf.numPages):
            # translation coordinates
            tx = 0
            ty = 0
            page = pdf.getPage(i)
            corner = [float(x) for x in page.mediaBox.getUpperRight()]
            if corner[0] > a4_width or corner[1] > a4_height:
                page.scaleBy(max(a4_width/corner[0], a4_height/corner[1]))
            elif corner[0] < a4_width or corner[1] < a4_height:
                tx = (a4_width - corner[0]) / 2
                ty = (a4_height - corner[1]) / 2
            convert.addBlankPage(a4_width, a4_height)
            convert.getPage(i).mergeTranslatedPage(page, tx, ty)
        output_stream = BytesIO()
        convert.write(output_stream)
        output_stream.seek(0)
        return base64.b64encode(output_stream.read())
