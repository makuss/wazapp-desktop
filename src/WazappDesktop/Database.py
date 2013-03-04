#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
from .helpers import checkForPeewee, CONFIG_PATH
checkForPeewee()
from peewee import SqliteDatabase, Model, CharField, DateTimeField, BooleanField, TextField, ForeignKeyField

_sqlite_db = SqliteDatabase(os.path.join(CONFIG_PATH, 'wazapp-desktop.db'))

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

class Contact(Model):
    class Meta:
        database = _sqlite_db

    conversationId = CharField(unique=True)
    name = CharField()
    pictureId = CharField(null=True)
    lastSeen = DateTimeField(null=True)
    available = makeVolatile(BooleanField)()

if not Contact.table_exists():
    Contact.create_table()

class Message(Model):
    class Meta:
        database = _sqlite_db
        order_by = ('timestamp',)

    contact = ForeignKeyField(Contact, related_name='messages')
    messageId = CharField(unique=True)
    sender = CharField()
    receiver = CharField()
    message = TextField()
    timestamp = DateTimeField()
    isRead = BooleanField(default=False)
    isSent = BooleanField(default=False)
    isDelivered = BooleanField(default=False)

if not Message.table_exists():
    Message.create_table()

def importData():
    import glob, datetime, codecs
    from .helpers import LOG_FILE_TEMPLATE, CONTACTS_FILE, readObjectFromFile

    oldContacts = readObjectFromFile(CONTACTS_FILE)
    importedContacts = 0
    importedMessages = 0

    base, ext = LOG_FILE_TEMPLATE.split('%s')
    for filename in glob.glob(base + '*' + ext):
        conversationId = filename.lstrip(base).rstrip(ext)
        name = oldContacts[conversationId].get('name')
        pictureId = oldContacts[conversationId].get('pictureId')
        if Contact.select().where(Contact.conversationId == conversationId).exists():
            contact = Contact.get(conversationId=conversationId)
        else:
            contact = Contact.create(conversationId=conversationId, name=name, pictureId=pictureId)
            importedContacts += 1

        with codecs.open(LOG_FILE_TEMPLATE % conversationId, 'r', 'utf8') as logfile:
            for line in logfile:
                messageId, timestamp, sender, receiver, message = line.rstrip('\n').split(';', 4)
                timestamp = float(timestamp)

                if not Message.select().where(Message.messageId == messageId).exists():
                    timestamp = datetime.datetime.fromtimestamp(timestamp)
                    Message.create(contact=contact, messageId=messageId, sender=sender, receiver=receiver, message=message, timestamp=timestamp, isRead=True)
                    importedMessages += 1

    print 'Database.importData(): imported %d contacts and %s messages' % (importedContacts, importedMessages)
