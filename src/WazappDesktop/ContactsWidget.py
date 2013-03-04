#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import datetime

from PyQt4.QtCore import pyqtSlot as Slot, pyqtSignal as Signal, QDir
from PyQt4.QtGui import QWidget, QListWidgetItem, QLineEdit, QInputDialog, QIcon, QMenu
from PyQt4.uic import loadUi

from .helpers import getConfig, setConfig
from .Contacts import Contacts

class ListWidgetItem(QListWidgetItem):

    def __lt__(self, otherItem):
        return self._sortingValue.lower() < otherItem._sortingValue.lower()

    def setOnline(self, online=True):
        if online:
            self.setIcon(QIcon.fromTheme('user-available'))
            self._sortingValue = ' ' + self.text()
        else:
            self.setIcon(QIcon.fromTheme('user-offline'))
            self._sortingValue = self.text()

    def setOffline(self):
        self.setOnline(False)

    def setGroup(self):
        self.setIcon(QIcon.fromTheme('internet-group-chat'))
        self._sortingValue = chr(ord(' ') - 1) + self.text()

    def setUnknown(self):
        self.setIcon(QIcon.fromTheme('dialog-question'))
        self._sortingValue = '~' + self.text()

class ContactsWidget(QWidget):
    start_chat_signal = Signal(str)

    def __init__(self):
        super(ContactsWidget, self).__init__()
        self._items = {}

        loadUi(os.path.join(QDir.searchPaths('ui')[0], 'ContactsWidget.ui'), self)

        self.importGoogleContactsButton.setIcon(QIcon.fromTheme('browser-download'))
        self.addContactButton.setIcon(QIcon.fromTheme('add'))

        self.contactsUpdated()
        Contacts.instance().contacts_updated_signal.connect(self.contactsUpdated)
        Contacts.instance().contact_status_changed_signal.connect(self.contactStatusChanged)
        Contacts.instance().edit_contact_signal.connect(self.editContact)

    def on_contactList_customContextMenuRequested(self, pos):
        item = self.contactList.itemAt(pos)
        if item is None:
            return
        menu = QMenu()
        results = {}
        results[menu.addAction('Edit Contact')] = (self.editContact, item._conversationId, item.text())
        results[menu.addAction('Remove Contact')] = (Contacts.instance().removeContact, item._conversationId)
        result = menu.exec_(self.contactList.mapToGlobal(pos))
        if result in results:
            handler = results[result][0]
            args = results[result][1:]
            handler(*args)

    @Slot()
    @Slot(str, str)
    def editContact(self, conversationId='', name=''):
        phone = conversationId.split('@')[0]
        if len(phone) == 0 or phone[0] != '+':
            phone = '+' + phone
        name, ok = QInputDialog.getText(self, 'Contact Name', 'Enter this contact\'s name', text=name)
        if not ok:
            return
        phone, ok = QInputDialog.getText(self, 'Contact Phone', 'Enter this contact\'s phone number\n(leading with a "+" and your country code)', text=phone)
        if not ok:
            return
        Contacts.instance().updateContact(phone, name)

    @Slot()
    def contactsUpdated(self):
        self.contactList.clear()
        for conversationId in Contacts.instance().getAllConversationIds():
            self.addContact(conversationId)

    @Slot()
    def on_addContactButton_clicked(self):
        self.editContact()

    def addContact(self, conversationId):
        name = Contacts.instance().getName(conversationId)
        item = ListWidgetItem(name)
        item._conversationId = conversationId
        self._items[conversationId] = item
        self.contactStatusChanged(conversationId)
        self.contactList.addItem(item)

    @Slot(str)
    def contactStatusChanged(self, conversationId):
        if conversationId not in self._items:
            print 'received contact status for unknown contact:', conversationId
            return

        item = self._items[conversationId]

        contacts = Contacts.instance()
        status = contacts.getStatus(conversationId)
        phone = contacts.getPhone(conversationId)
        if contacts.isGroup(conversationId):
            item.setToolTip('Group: %s' % (phone))
            item.setGroup()
        else:
            if status.get('available') is None:
                item.setToolTip('Phone: +%s\nno information available' % (phone))
                item.setUnknown()
            else:
                item.setOnline(status['available'])
                formattedDate = datetime.datetime.fromtimestamp(status['lastSeen']).strftime('%d-%m-%Y %H:%M:%S')
                phone = conversationId.split('@')[0]
                item.setToolTip('Phone: +%s\nAvailable: %s (last seen %s)' % (phone, status['available'], formattedDate))

    @Slot(QListWidgetItem)
    def on_contactList_itemDoubleClicked(self, item):
        self.start_chat_signal.emit(item._conversationId)

    @Slot()
    def on_importGoogleContactsButton_clicked(self):
        googleUsername, ok = QInputDialog.getText(self, 'Google Username', 'Enter your Google username/email', text=getConfig('googleUsername', ''))
        if not ok:
            return
        googlePassword, ok = QInputDialog.getText(self, 'Google Password', 'Enter your Google password', mode=QLineEdit.Password)
        if not ok:
            return
        setConfig('googleUsername', googleUsername)
        Contacts.instance().importGoogleContacts(googleUsername, googlePassword)
