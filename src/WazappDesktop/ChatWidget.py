#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import re
import datetime
import webbrowser

from PyQt4.QtCore import Qt, pyqtSlot as Slot, pyqtSignal as Signal, QPoint, QDir, QUrl, QTimer
from PyQt4.QtGui import QDockWidget, QMenu, QIcon, QCursor
from PyQt4.QtWebKit import QWebPage, QWebElement
from PyQt4.uic import loadUi

from .helpers import getConfig
from .Contacts import Contacts
from .ContactDB import ContactDB

url_pattern1 = re.compile(r"(^|[\n ])(([\w]+?://[\w\#$%&~.\-;:=,?@\[\]+]*)(/[\w\#$%&~/.\-;:=,?@\[\]+]*)?)", re.IGNORECASE | re.DOTALL)
url_pattern2 = re.compile(r"(^|[\n ])(((www|ftp)\.[\w\#$%&~.\-;:=,?@\[\]+]*)(/[\w\#$%&~/.\-;:=,?@\[\]+]*)?)", re.IGNORECASE | re.DOTALL)
def url2link(text):
    text = url_pattern1.sub(r'\1<a href="\2" target="_blank">\2</a>', text)
    text = url_pattern2.sub(r'\1<a href="http:/\2" target="_blank">\2</a>', text)
    return text


class ChatWidget(QDockWidget):
    send_message_signal = Signal(str, unicode)
    scroll_to_bottom_signal = Signal()
    show_message_signal = Signal(str, str, float, str, str, str)
    show_history_message_signal = Signal(str, str, datetime.datetime, str, str, str, bool)
    show_history_since_signal = Signal(float)
    show_history_num_messages_signal = Signal(int)
    has_unread_message_signal = Signal(str, bool)
    paragraphIdFormat = 'p%s'
    paragraphFormat = '''
        <p id=%(paragraphId)s>
            <span class="time">[%(formattedTime)s] </span>
            <a href="%(senderPic)s"><img height="20px" src="%(senderPic)s"></a>
            <a href="wa:contactMenu?jid=%(senderJid)s&name=%(senderName)s" class="%(nameClass)s">%(senderDisplayName)s: </a>
            <span class="message">%(message)s</span>
        </p>
    '''

    def __init__(self, conversationId):
        super(ChatWidget, self).__init__()
        self._conversationId = conversationId
        self._windowTitle = Contacts.instance().getName(self._conversationId)
        self._ownJid = Contacts.instance().phoneToConversationId(getConfig('countryCode') + getConfig('phoneNumber'))
        self._defaultContactPicture = '/%s/im-user.png' % QDir.searchPaths('icons')[0]
        self._chatViewUrl = QUrl('file://%s/ChatView.html' % QDir.searchPaths('html')[0])
        self._historyTimestamp = datetime.date.today()

        self._scrollTimer = QTimer()
        self._scrollTimer.setSingleShot(True)
        self._scrollTimer.timeout.connect(self.on_scrollToBottom)
        self.scroll_to_bottom_signal.connect(self.on_scrollToBottom, Qt.QueuedConnection)

        loadUi(os.path.join(QDir.searchPaths('ui')[0], 'ChatWidget.ui'), self)
        self.setWindowTitle(self._windowTitle)
        self.historyButton.setIcon(QIcon.fromTheme('clock'))

        self.visibilityChanged.connect(self.on_visibilityChanged)
        self.chatView.page().setLinkDelegationPolicy(QWebPage.DelegateAllLinks)
        self.__on_messageText_keyPressEvent = self.messageText.keyPressEvent
        self.messageText.keyPressEvent = self.on_messageText_keyPressEvent
        self.show_message_signal.connect(self.showMessage)
        self.show_history_message_signal.connect(self.showMessage)
        self.show_history_since_signal.connect(self.showHistorySince)
        self.show_history_num_messages_signal.connect(self.showHistoryNumMessages)
        self.has_unread_message_signal.connect(self.unreadMessage)

        self.reloadChatView()
        self.showHistorySince(datetime.date.today(), minMessage=3, maxMessages=10)

    def reloadChatView(self):
        self._bodyElement = QWebElement()
        self.chatView.load(self._chatViewUrl)
        self.showHistorySince(self._historyTimestamp)

    def on_chatView_customContextMenuRequested(self, pos):
        menu = QMenu()
        results = {}
        results[menu.addAction('Dump HTML')] = self.dumpHtml
        results[menu.addAction('Refresh')] = self.reloadChatView
        result = menu.exec_(self.chatView.mapToGlobal(pos))
        if result in results:
            results[result]()

    def dumpHtml(self):
        print self.chatView.page().mainFrame().toHtml()

    def on_visibilityChanged(self, visible):
        if visible:
            self.has_unread_message_signal.emit(self._conversationId, False)
            self.messageText.setFocus(Qt.OtherFocusReason)

    @Slot()
    def on_historyButton_pressed(self):
        menu = QMenu()
        results = {
            menu.addAction('Today'): datetime.date.today(),
            menu.addAction('Last 24 Hours'): datetime.datetime.now() - datetime.timedelta(1),
            menu.addAction('Last 7 Days'): datetime.datetime.now() - datetime.timedelta(7),
            menu.addAction('Last 30 Days'): datetime.datetime.now() - datetime.timedelta(30),
            menu.addAction('Last 6 Month'): datetime.datetime.now() - datetime.timedelta(30 * 6),
            menu.addAction('Last Year'): datetime.datetime.now() - datetime.timedelta(365),
            menu.addAction('All Time'): 0,
            menu.addAction('None'): datetime.datetime.now(),
        }
        result = menu.exec_(self.historyButton.mapToGlobal(QPoint(0, self.historyButton.height())))
        if result in results:
            self.showHistorySince(results[result])

    @Slot(float)
    @Slot(datetime.date)
    @Slot(datetime.datetime)
    def showHistorySince(self, timestamp, minMessage=0, maxMessages=10000):
        self._historyTimestamp = timestamp
        if type(timestamp) is float:
            timestamp = datetime.datetime.fromtimestamp(timestamp)
        messages = ContactDB.instance().getMessageList(self._conversationId, since=timestamp)
        if messages is None:
            numMessages = 0
        else:
            numMessages = len(messages)#.count()
        self.showHistoryNumMessages(min(max(minMessage, numMessages), maxMessages))

    @Slot(int)
    def showHistoryNumMessages(self, numMessages):
        #print numMessages, self._conversationId
        self.clearChatView()
        # queue showing of messages until page is loaded
        self._showNumMessages = numMessages
        if self._bodyElement.isNull():
            return
        self._showHistoryMessages()

    def _showHistoryMessages(self):
        if self._bodyElement.isNull():
            print '_showHistoryMessages(): bodyElement is Null!'
            return
        # show last messages
        if self._showNumMessages > 0:
            for message in ContactDB.instance().getMessageList(self._conversationId, numMessages=self._showNumMessages):
                self.show_history_message_signal.emit(self._conversationId, message.messageId, message.timestamp, message.sender, message.receiver, message.message, message.isRead)
            self._showNumMessages = 0

    def clearChatView(self):
        self._lastSender = ''
        self._lastDate = ''
        self._showNumMessages = 0
        self._bodyElement.setInnerXml('')

    @Slot()
    @Slot(bool)
    def on_chatView_loadFinished(self, ok=True):
        self._bodyElement = self.chatView.page().mainFrame().documentElement().findFirst('body')
        # check that the body element is really loaded, otherwise try again later
        if self._bodyElement.isNull():
            QTimer.singleShot(100, self.on_chatView_loadFinished)
            return
        self._showHistoryMessages()

    @Slot(str, bool)
    def unreadMessage(self, conversationId, unread):
        if unread:
            self.setWindowTitle('*' + self._windowTitle)
        else:
            self.setWindowTitle(self._windowTitle)

    def on_messageText_keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not bool(event.modifiers() & Qt.ShiftModifier):
            self.on_sendButton_clicked()
            event.accept()
        else:
            self.__on_messageText_keyPressEvent(event)

    def on_command_contactMenu(self, parameters):
        conversationId = parameters.get('jid')
        if conversationId is None:
            print 'on_command_contactMenu(): missing parameter "jid"'
            return
        knownContact = len(parameters.get('name', '')) > 0
        menu = QMenu()
        results = {
            menu.addAction('Edit Contact' if knownContact else 'Add Contact'): (Contacts.instance().edit_contact_signal.emit, (parameters.get('jid', ''), parameters['name'])),
        }
        result = menu.exec_(QCursor.pos())
        if result in results:
            results[result][0](*results[result][1])


    def on_chatView_linkClicked(self, url):
        if url.scheme() == 'wa':
            command = url.path()
            parameters = dict(url.queryItems())
            handler = getattr(self, 'on_command_%s' % command)
            if handler is None:
                print 'on_chatView_linkClicked(): unknown command: %s' % (command)
            else:
                handler(parameters)
        else:
            webbrowser.open(url.toString())

    @Slot()
    def on_scrollToBottom(self):
        bottom = self.chatView.page().mainFrame().scrollBarMaximum(Qt.Vertical)
        self.chatView.page().mainFrame().setScrollBarValue(Qt.Vertical, bottom)

    @Slot()
    def on_sendButton_clicked(self):
        message = self.messageText.toPlainText()
        self.messageText.clear()
        self.send_message_signal.emit(self._conversationId, message)

    def showMessage(self, conversationId, messageId, timestamp, senderJid, receiver, message, isRead=False):
        if len(message) == 0:
            return
        # make sure this message goes in the right chat view
        if conversationId != self._conversationId:
            print 'showMessage(): message to "%s" not for me "%s"' % (conversationId, self._conversationId)
            return
        # if html page is not loaded yet, queue this message
        if self._bodyElement.isNull():
            self._showNumMessages += 1
            return

        parameters = {}
        parameters['message'] = message
        if type(timestamp) is float:
            timestamp = datetime.datetime.fromtimestamp(timestamp)
        parameters['formattedDate'] = timestamp.strftime('%A, %d %B %Y')
        parameters['formattedTime'] = timestamp.strftime('%H:%M:%S')
        if self._lastDate != parameters['formattedDate']:
            self._lastDate = parameters['formattedDate']
            self._bodyElement.appendInside('<p class="date">%s</p>' % parameters['formattedDate'])

        parameters['senderJid'] = senderJid
        parameters['senderName'] = Contacts.instance().getName(senderJid)
        parameters['senderDisplayName'] = parameters['senderName']

        parameters['senderPic'] = Contacts.instance().getContactPicture(senderJid)
        if parameters['senderPic'] is None:
            parameters['senderPic'] = self._defaultContactPicture
        parameters['senderPic'] = 'file://' + parameters['senderPic']

        # set class for name element, depending if senderJid is in contacts and if its or own jid
        if parameters['senderJid'] == parameters['senderName']:
            parameters['senderDisplayName'] = parameters['senderName'].split('@')[0]
            parameters['senderName'] = ''
            parameters['nameClass'] = 'unknown'
        elif parameters['senderJid'] == self._ownJid:
            parameters['nameClass'] = 'myname'
        else:
            parameters['nameClass'] = 'name'

        # don't show sender name again, if multiple consecutive messages from one sender
        if parameters['senderDisplayName'] == self._lastSender:
            parameters['senderDisplayName'] = '...'
        else:
            self._lastSender = parameters['senderDisplayName']

        # parse plain text messages for links
        if '</a>' not in parameters['message']:
            parameters['message'] = url2link(parameters['message'])

        # parse plain text messages for new lines
        if '<br>' not in parameters['message']:
            parameters['message'] = '<br>'.join(parameters['message'].split('\n'))

        parameters['paragraphId'] = self.paragraphIdFormat % messageId
        self._bodyElement.appendInside(self.paragraphFormat % parameters)

        self.chatView.page().mainFrame().evaluateJavaScript('elementAdded("%s"); null' % parameters['paragraphId'])

        # set scroll timer to scroll down in 100ms, after the new text is hopefully rendered (any better solutions?)
        self._scrollTimer.start(100)

        if not isRead and not (self.isVisible() and self.isActiveWindow()):
            self.has_unread_message_signal.emit(self._conversationId, True)

    @Slot(str, str, str)
    def messageStatusChanged(self, conversationId, messageId, status):
        paragraphId = self.paragraphIdFormat % messageId
        messageElement = self._bodyElement.findFirst('p#%s' % paragraphId)
        if not messageElement.isNull():
            messageElement.setAttribute('class', status)
