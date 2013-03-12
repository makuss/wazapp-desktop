#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
from .helpers import checkForPeewee, DATABASE_FILE
checkForPeewee()
from peewee import SqliteDatabase, Model, CharField, DateTimeField, BooleanField, TextField, ForeignKeyField

_sqlite_db = SqliteDatabase(DATABASE_FILE)

def makeVolatile(BaseClass):
    class VolatileClass(BaseClass):
        def __init__(self, *args, **kwargs):
            kwargs['null'] = True
            super(VolatileClass, self).__init__(*args, **kwargs)
            self.__volatile_value = None

        def db_value(self, value):
            self.__volatile_value = value
            return None

        def python_value(self, value):
            return self.__volatile_value

    return VolatileClass

class ContactModel(Model):
    class Meta:
        database = _sqlite_db

    conversationId = CharField(unique=True)
    name = CharField()
    pictureId = CharField(null=True)
    lastSeen = DateTimeField(null=True)
    available = makeVolatile(BooleanField)()

if not ContactModel.table_exists():
    ContactModel.create_table()


class MessageModel(Model):
    class Meta:
        database = _sqlite_db
        order_by = ('timestamp',)

    contact = ForeignKeyField(ContactModel, related_name='messages')
    messageId = CharField(unique=True)
    sender = CharField()
    receiver = CharField()
    message = TextField()
    timestamp = DateTimeField()
    isRead = BooleanField(default=False)
    isSent = BooleanField(default=False)
    isDelivered = BooleanField(default=False)

if not MessageModel.table_exists():
    MessageModel.create_table()

def convertLegacyDatabases():
    import glob, datetime, codecs
    from .helpers import LOG_FILE_TEMPLATE, CONTACTS_FILE, readObjectFromFile

    if os.path.isfile(CONTACTS_FILE):
        oldContacts = readObjectFromFile(CONTACTS_FILE)
        importedContacts = 0
        for conversationId in oldContacts.keys():
            name = oldContacts.get(conversationId, {}).get('name', conversationId)
            pictureId = oldContacts.get(conversationId, {}).get('pictureId')
            if ContactModel.select().where(ContactModel.conversationId == conversationId).exists():
                contact = ContactModel.get(conversationId=conversationId)
            else:
                contact = ContactModel.create(conversationId=conversationId, name=name, pictureId=pictureId)
                importedContacts += 1
        print 'Database.convertLegacyDatabases(): imported %d contacts' % (importedContacts)
        print 'Database.convertLegacyDatabases(): please delete old contacts file:', CONTACTS_FILE
    else:
        oldContacts = {}

    importedMessages = 0
    base, ext = LOG_FILE_TEMPLATE.split('%s')
    historyFilePattern = base + '*' + ext
    historyFiles = glob.glob(historyFilePattern)
    if historyFiles:
        for filename in historyFiles:
            conversationId = filename.lstrip(base).rstrip(ext)
            name = oldContacts.get(conversationId, {}).get('name', conversationId)
            pictureId = oldContacts.get(conversationId, {}).get('pictureId')
            if ContactModel.select().where(ContactModel.conversationId == conversationId).exists():
                contact = ContactModel.get(conversationId=conversationId)
            else:
                contact = ContactModel.create(conversationId=conversationId, name=name, pictureId=pictureId)

            with codecs.open(LOG_FILE_TEMPLATE % conversationId, 'r', 'utf8') as logfile:
                for line in logfile:
                    messageId, timestamp, sender, receiver, message = line.rstrip('\n').split(';', 4)
                    timestamp = float(timestamp)

                    if not MessageModel.select().where(MessageModel.messageId == messageId).exists():
                        timestamp = datetime.datetime.fromtimestamp(timestamp)
                        MessageModel.create(contact=contact, messageId=messageId, sender=sender, receiver=receiver, message=message, timestamp=timestamp, isRead=True)
                        importedMessages += 1

        print 'Database.convertLegacyDatabases(): imported %s messages' % (importedMessages)
        print 'Database.convertLegacyDatabases(): please delete old history files:', historyFilePattern
