#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import base64
import re

from PyQt4.QtGui import QMessageBox
from PyQt4.QtCore import QObject, pyqtSlot as Slot, pyqtSignal as Signal

from .helpers import PICTURE_CACHE_PATH, getConfig
from .ContactDB import ContactDB

from Yowsup.Contacts.contacts import WAContactsSyncRequest

class Contacts(QObject):
    contacts_updated_signal = Signal()
    contact_status_changed_signal = Signal(str)
    edit_contact_signal = Signal(str, str)
    userIdFormat = '%s@s.whatsapp.net'
    groupIdFormat = '%s@g.us'

    @staticmethod
    def instance():
        return _instance

    def __init__(self):
        super(Contacts, self).__init__()
        self._enableUpdateSignal()

    def _enableUpdateSignal(self, enabled=True):
        ContactDB.instance().contacts_updated_signal.connect(self.contacts_updated_signal)
        self.contacts_updated_signal.emit()

    def phoneToConversationId(self, phoneOrGroup):
        # if there is an @, it's got to be a jid already
        if '@' in phoneOrGroup:
            return phoneOrGroup
        if self.isGroup(phoneOrGroup):
            return self.groupIdFormat % phoneOrGroup
        # strip all non numeric chars
        phoneOrGroup = re.sub('[\D]+', '', phoneOrGroup)
        return self.userIdFormat % phoneOrGroup

    def getPhone(self, conversationId):
        return conversationId.split('@')[0]

    def isGroup(self, conversationId):
        phone = self.getPhone(conversationId)
        # if there is exactly one - followed by 10 digits, it's got to be a group number
        return phone.count('-') == 1 and phone[-11] == '-'

    def getAllConversationIds(self):
        return [c.conversationId for c in ContactDB.instance().getAll()]

    def removeContact(self, conversationId):
        ContactDB.instance().delete(conversationId)

    def setContactName(self, conversationId, name):
        ContactDB.instance().updateOrCreate(conversationId, name=name)

    def getName(self, conversationId):
        contact = ContactDB.instance().get(conversationId)
        if contact is None:
            return conversationId
        return contact.name

    def setContactPictureId(self, conversationId, pictureId):
        ContactDB.instance().updateOrCreate(conversationId, pictureId=pictureId)

    def getContactPicture(self, conversationId):
        contact = ContactDB.instance().get(conversationId)
        if contact is None or contact.pictureId is None:
            return None
        return '%s.jpeg' % os.path.join(PICTURE_CACHE_PATH, contact.pictureId)

    def getStatus(self, conversationId):
        contact = ContactDB.instance().get(conversationId)
        if contact is None:
            return {'available': None, 'lastSeen': 0}
        return {'available': contact.available, 'lastSeen': contact.lastSeen}

    @Slot(str, str)
    def updateContact(self, phoneOrGroup, name):
        phoneOrGroup = phoneOrGroup.split('@', 1)[0]
        if phoneOrGroup.count('-') == 1 and phoneOrGroup[-11] == '-':
            phoneOrGroup = phoneOrGroup.strip(' ').lstrip('+')
        else:
            waPhones = self.getWAUsers([phoneOrGroup]).values()
            if len(waPhones) > 0:
                phoneOrGroup = waPhones[0]
            else:
                text = 'WhatsApp did not know about the phone number "%s"!\n' % (phoneOrGroup)
                text += 'Please check that the number starts with a "+" and your country code.'
                QMessageBox.warning(None, 'WhatsApp User Not Found', text)
                self.edit_contact_signal.emit(phoneOrGroup, name)
                return
        self.setContactName(self.phoneToConversationId(phoneOrGroup), name)

    @Slot(str, object, object)
    def contactStatusChanged(self, conversationId, available, lastSeen):
        if available is not None:
            ContactDB.instance().updateOrCreate(conversationId, available=available)
        if lastSeen is not None:
            ContactDB.instance().updateOrCreate(conversationId, lastSeen=lastSeen)
        self.contact_status_changed_signal.emit(conversationId)

    def getWAUsers(self, phoneNumbers):
        waUsers = {}
        waUsername = str(getConfig('countryCode') + getConfig('phoneNumber'))
        waPassword = base64.b64decode(getConfig('password'))
        waContactsSync = WAContactsSyncRequest(waUsername, waPassword, phoneNumbers)
        try:
            results = waContactsSync.send()
        except Exception as e:
            QMessageBox.warning(None, 'Failure', 'Failed to connect to WhatsApp server.\nError was:\n%s' % (e))
            return waUsers

        for entry in results.get('c', []):
            hasWhatsApp = bool(entry['w'])
            if hasWhatsApp:
                requestedPhone = entry['p']
                phone = entry['n']
                waUsers[requestedPhone] = phone
        return waUsers

    @Slot(str, str)
    def importGoogleContacts(self, googleUsername, googlePassword):
        import gdata.contacts.client
        gd_client = gdata.contacts.client.ContactsClient(source='GoogleInc-ContactsPythonSample-1')
        try:
            gd_client.ClientLogin(googleUsername, googlePassword, gd_client.source)
        except gdata.client.BadAuthentication as e:
            QMessageBox.warning(None, 'Authentication Failure', 'Failed to authenticate with Google for user:\n%s\n\nError was:\n%s' % (googleUsername, e))
            return
        except Exception as e:
            QMessageBox.warning(None, 'Failure', 'Failed to connect to Google.\nError was:\n%s' % (e))
            return

        query = gdata.contacts.client.ContactsQuery()
        query.max_results = 10000

        googleContacts = {}
        feed = gd_client.GetContacts(q=query)
        for entry in feed.entry:
            for number in entry.phone_number:
                googleContacts[number.text] = entry.title.text

        waUsers = self.getWAUsers(googleContacts.keys())
        self._enableUpdateSignal(enabled=False)
        for googlePhone, waPhone in waUsers.items():
            name = googleContacts[googlePhone]
            self.setContactName(self.phoneToConversationId(waPhone), name)
        self._enableUpdateSignal()

        QMessageBox.information(None, 'Import successful', 'Found %d WhatsApp users in your %d Google contacts.' % (len(waUsers), len(googleContacts)))

_instance = Contacts()
