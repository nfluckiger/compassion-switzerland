# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2018 Compassion CH (http://www.compassion.ch)
#    Releasing children from poverty in Jesus' name
#    @author: Samuel Fringeli <samuel.fringeli@me.com>
#    The licence is in the file __manifest__.py
#
##############################################################################

from odoo.addons.sponsorship_compassion.tests.test_sponsorship_compassion \
    import BaseSponsorshipTest

import logging

logger = logging.getLogger(__name__)



class BasePartnerCommunicationTest(BaseSponsorshipTest):
    def setUp(self):
        super(BasePartnerCommunicationTest, self).setUp()

        # Create a child and get the project associated
        child = self.create_child('PE012304567')

        # Creation of the sponsorship contract
        sp_group = self.create_group({'partner_id': self.michel.id})
        self.sponsorship = self.create_contract(
            {
                'partner_id': self.michel.id,
                'group_id': sp_group.id,
                'child_id': child.id,
            },
            [{'amount': 50.0}]
        )

    def test_child_attachments(self):
        pass
