#!/usr/bin/python
# -*- coding: utf-8 -*-

import datetime

from .Database import ContactModel, MessageModel

from PyQt4.QtCore import QObject, pyqtSignal as Signal

class ContactDB(QObject):
    contacts_updated_signal = Signal()
    delete_signal = Signal(str)
    update_or_create_signal = Signal(str, dict)
    add_message_signal = Signal(str, str, float, str, str, str)

    @staticmethod
    def instance():
        return _instance

    def __init__(self):
        super(ContactDB, self).__init__()
        self.delete_signal.connect(self._delete)
        self.update_or_create_signal.connect(self._updateOrCreate)
        self.add_message_signal.connect(self._addMessage)

    def getAll(self):
        return list(ContactModel.select())

    def get(self, conversationId):
        if ContactModel.select().where(ContactModel.conversationId == conversationId).exists():
            return ContactModel.get(conversationId=conversationId)
        return None

    def _delete(self, conversationId):
        ContactModel.delete().where(ContactModel.conversationId == conversationId).execute()

    def delete(self, conversationId):
        self.delete_signal.emit(conversationId)
        self.contacts_updated_signal.emit()

    def _updateOrCreate(self, conversationId, updateDict):
        if ContactModel.select().where(ContactModel.conversationId == conversationId).exists():
            contact = ContactModel.get(conversationId=conversationId)
            if updateDict:
                for key, value in updateDict.items():
                    setattr(contact, key, value)
                contact.save()
                self.contacts_updated_signal.emit()
            return contact
        else:
            if 'name' not in updateDict:
                updateDict['name'] = conversationId
            contact = ContactModel.create(conversationId=conversationId, **updateDict)
            self.contacts_updated_signal.emit()
            return contact

    def updateOrCreate(self, conversationId, **kwargs):
        self.update_or_create_signal.emit(conversationId, kwargs)

    def getMessageList(self, conversationId, numMessages=None, since=None):
        if not ContactModel.select().where(ContactModel.conversationId == conversationId).exists():
            return list()
        messages = ContactModel.get(conversationId=conversationId).messages
        if since is not None:
            return list(messages.where(MessageModel.timestamp > since))
        if numMessages is not None:
            return list(messages)[-numMessages:]
        return list(messages)

    def _addMessage(self, conversationId, messageId, timestamp, sender, receiver, message):
        contact = ContactDB.instance()._updateOrCreate(conversationId, {})
        timestamp = datetime.datetime.fromtimestamp(timestamp)
        MessageModel.create(contact=contact, messageId=messageId, sender=sender, receiver=receiver, message=message, timestamp=timestamp, isRead=False)

    def addMessage(self, conversationId, messageId, timestamp, sender, receiver, message):
        if MessageModel.select().where(MessageModel.messageId == messageId).exists():
            print 'ContactDB.addMessage(): received duplicate message:', conversationId, messageId, timestamp, sender, receiver, message
            return None
        self.add_message_signal.emit(conversationId, messageId, timestamp, sender, receiver, message)
        return messageId


_instance = ContactDB()
