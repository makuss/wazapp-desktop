#!/usr/bin/python
# -*- coding: utf-8 -*-

import datetime

from .Database import ContactModel, MessageModel

from PyQt4.QtCore import QObject

class ContactDB(QObject):

    @staticmethod
    def instance():
        return _instance

    def getAll(self):
        return list(ContactModel.select())

    def get(self, conversationId):
        if ContactModel.select().where(ContactModel.conversationId == conversationId).exists():
            return ContactModel.get(conversationId=conversationId)
        return None

    def delete(self, conversationId):
        ContactModel.delete().where(ContactModel.conversationId == conversationId).execute()

    def updateOrCreate(self, conversationId, **kwargs):
        if ContactModel.select().where(ContactModel.conversationId == conversationId).exists():
            contact = ContactModel.get(conversationId=conversationId)
            if kwargs:
                for key, value in kwargs.items():
                    setattr(contact, key, value)
                contact.save()
            return contact
        else:
            if 'name' not in kwargs:
                kwargs['name'] = conversationId
            contact = ContactModel.create(conversationId=conversationId, **kwargs)
            return contact

    def getMessageList(self, conversationId, numMessages=None, since=None):
        if not ContactModel.select().where(ContactModel.conversationId == conversationId).exists():
            return list()
        messages = ContactModel.get(conversationId=conversationId).messages
        if since is not None:
            return list(messages.where(MessageModel.timestamp > since))
        if numMessages is not None:
            return list(messages)[-numMessages:]
        return list(messages)

    def addMessage(self, conversationId, messageId, timestamp, sender, receiver, message):
        if MessageModel.select().where(MessageModel.messageId == messageId).exists():
            # if message is already in the logs and it is from my self, mark it as the answer message
            if sender == receiver:
                messageId += '*'
            else:
                print 'ContactDB.addMessage(): received duplicate message:', conversationId, messageId, timestamp, sender, receiver, message
                return None
        contact = self.updateOrCreate(conversationId)
        timestamp = datetime.datetime.fromtimestamp(timestamp)
        MessageModel.create(contact=contact, messageId=messageId, sender=sender, receiver=receiver, message=message, timestamp=timestamp, isRead=False)
        return messageId


_instance = ContactDB()
