#!/usr/bin/env python

# Copyright Grant Edwards
# grant.b.edwards@gmail.com
#
# This program is released under the terms of the Gnu General Public
# License version 2 (GPLv2)
#
# http://www.gnu.org/licenses/gpl-2.0.html

version = "0.21"

import pygtk
pygtk.require('2.0')
import gtk,gobject
import threading, time, sys, shlex, subprocess, Queue, traceback, os, ConfigParser
import ssl
import imaplib2
from optparse import OptionParser

parser = OptionParser()
parser.add_option("-l", "--log", dest="logfilename",default=None,
                  help="write log to FILE", metavar="FILE")
parser.add_option("-v", "--verbose", dest="verbose", type="int", default=0,
                  help="verbosity level", metavar="LEVEL")
parser.add_option("-g", "--geometry", dest="geometry", default="",
                  help="X11 geometry string", metavar="GEOMETRY")
parser.add_option("-f", "--config-file", dest="configfile", default=os.path.expanduser('~/.imapnotifyrc'),
                  help="Config file path")

option,args = parser.parse_args()

gobject.threads_init()
running = True

global logfile
logfile = sys.stdout
if option.logfilename:
    logfile = open(option.logfilename,'w')
def log(level,s):
    if level <= option.verbose:
        logfile.write(s)
        logfile.write('\n')
        logfile.flush()

class Mailbox:
    def __init__(self,name):
        self.name = name
        self.boxname = "INBOX"
        self.polltime = 1200
        self.username = None
        self.password = None
        self.server = None
        self.cmd = None
        self.delayedexpunge = False
        self.ssl_version = None
        self.connection_status_only = None

class MyButton(gtk.Button):

    def __init__(self,label,*args,**kwargs):
        gtk.Button.__init__(self,label,*args,**kwargs)
        self.__baseLabel__ = label

    def _setLabelStyle(self,style):
        self.get_child().set_style(style)

    def setLabelStyle(self,style):
        gobject.idle_add(self._setLabelStyle,style)

    def setLabelSuffix(self, s):
        gobject.idle_add(self.set_label, self.__baseLabel__+s)

    def setTooltipText(self, s):
        gobject.idle_add(self.set_tooltip_text, s)

class Notifier:

    def fakeIdle(self, timeout=29*60, callback=None):
        log(2,"starting fake idle command")
        time.sleep(timeout)
        log(2,"fake idle command terminated")
        if callback:
            callback( (('OK', ['IDLE terminated (Success)']), None, None) )

    def monitorMailbox(self,mailbox):
        global running, tooltipsEnabled, showcountEnabled
        log(1,"starting monitor for %s" % mailbox.name)
        mailbox.eventQueue = Queue.Queue(maxsize=5)
        threading.currentThread().setName(mailbox.name + ' monitor')

        def mlog(level,s):
            log(level,(mailbox.name+" "+s))

        def idleCallback(args):
            mlog(1,"idleCallback: %s" % str(args))
            mailbox.eventQueue.put_nowait('IDLEDONE')

        while running:
            try:
                mlog(1,"starting imap session")
                mailbox.button.setLabelStyle(self.style_yellow)

                imap = imaplib2.IMAP4_SSL(mailbox.server,identifier=mailbox.name,debug=max(0,option.verbose-1),debug_file=logfile,ssl_version=mailbox.ssl_version)
                imap.LOGIN(mailbox.username, mailbox.password)
                assert imap.state == imaplib2.AUTH
                mlog(1,"logged in")
                imap.EXAMINE(mailbox.boxname)
                assert imap.state == imaplib2.SELECTED
                mlog(1,"selected %s" % mailbox.boxname)
                mailbox.button.setLabelStyle(self.style_normal)
                mailbox.eventQueue.put_nowait('POLL')
                while running  and imap.state == imaplib2.SELECTED:
                    event = mailbox.eventQueue.get()
                    mlog(1,"got event %s" % event)
                    if event == 'SHUTDOWN':
                        imap.logout()
                        imap.shutdown()
                        break

                    if event == 'CMDFINISHED' and mailbox.delayedexpunge:
                        mlog(1,'delayed expunge')
                        polltime = 1
                    else:
                        time.sleep(0.1)
                        polltime = mailbox.polltime
                        ret, data = imap.SEARCH(None, 'UNSEEN')
                        mlog(1,"unseen: %s" % ((ret,data),))
                        if data[0] and not mailbox.connection_status_only:
                            count = len(data[0].split())
                            suffix = " %d" % count
                            style = self.style_red
                        else:
                            count = 0
                            suffix = ""
                            style = self.style_normal

                        if showcountEnabled:
                            mailbox.button.setLabelSuffix(suffix)

                        if tooltipsEnabled:
                            mailbox.button.setTooltipText("%s unseen" % count)

                        mailbox.button.setLabelStyle(style)


                    # flush pending events
                    while not mailbox.eventQueue.empty():
                        event = mailbox.eventQueue.get_nowait()
                        if event == 'SHUTDOWN':
                            imap.logout()
                            imap.shutdown()
                        else:
                            mlog(1,"discarding event: %s" % event)

                    if imap.state == imaplib2.SELECTED:
                        if 'IDLE' in imap.capabilities:
                            imap.idle(timeout=polltime, callback=idleCallback)
                        else:
                            threading.Thread(target=self.fakeIdle, args=(polltime,idleCallback))
                        
                        mlog(1,"sent IDLE command")

                    if running:
                        time.sleep(1)  # make sure we don't hog the CPU when something goes wrong.

            except:
                mailbox.button.setLabelStyle(self.style_yellow)
                mlog(0,"monitorMailbox got exception")
                mlog(0,"------------------------------------------------------------")
                mlog(0,traceback.format_exc())
                mlog(0,"------------------------------------------------------------")
                try:
                    mlog(0,"monitorMailbox shutting down connection")
                    imap.shutdown()
                    mlog(0,"monitorMailbox connection shutdown complete")
                except:
                    mlog(0,"monitorMailbox ignoring exception during shutdown")
                    pass

            if running:
                mailbox.button.setLabelStyle(self.style_yellow)
                mlog(1,"connection died -- waiting 10 seconds before attempting to re-connect")
                time.sleep(10) # don't attempt to re-connect too frequently

        mailbox.button.setLabelStyle(self.style_yellow)
        mlog(1,"monitorMailbox terminating")

    def runcmd(self, mailbox):
        log(1,"%s running command %s" % (mailbox.name,mailbox.cmd))
        if mailbox.cmd:
            subprocess.call(mailbox.cmd)
        mailbox.eventQueue.put_nowait("CMDFINISHED")

    def click(self, button, mailbox):
        log(1,"%s click on %s" % (mailbox.name,button))
        button._setLabelStyle(self.style_normal)
        threading.Thread(target=self.runcmd,args=(mailbox,)).start()

    def middleclick(self, button, mailbox):
        log(1,"%s middle-click on %s" % (mailbox.name,button))
        button._setLabelStyle(self.style_normal)

    def shutdown(self):
        log(1,"shutting down")
        global running
        running = False
        for mailbox in self.mailboxes:
            mailbox.eventQueue.put_nowait('SHUTDOWN')
        log(1,"done")


    def delete_event(self, widget, event, data=None):
        self.shutdown()
        return False

    def __init__(self,mailboxes):

        self.mailboxes = mailboxes

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title(config.get('Application','title'))
        self.window.set_decorated(config.getboolean('Application','decorated'))
        if config.getboolean('Application','stick'):
            self.window.stick()
        if config.getboolean('Application','desktop'):
            self.window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DESKTOP)
        self.window.set_keep_above(config.getboolean('Application','keepontop'))
        self.window.set_keep_below(config.getboolean('Application','keeponbottom'))
        self.window.set_skip_taskbar_hint(config.getboolean('Application','skiptaskbar'))
        self.window.set_skip_pager_hint(config.getboolean('Application','skippager'))

        self.window.parse_geometry(option.geometry)

        #self.window.set_gravity(gtk.gdk.GRAVITY_NORTH_WEST)
        #self.window.move(0,0)

        self.window.connect("delete_event", self.delete_event)
        self.window.set_border_width(0)

        self.box = gtk.VBox(False, 0)
        self.window.add(self.box)

        red = self.window.get_colormap().alloc_color("red")
        yellow = self.window.get_colormap().alloc_color("yellow")
        self.style_normal = gtk.Button("").get_style().copy()
        self.style_red = self.style_normal.copy()
        self.style_yellow = self.style_normal.copy()
        for s in gtk.STATE_NORMAL,gtk.STATE_ACTIVE,gtk.STATE_SELECTED,gtk.STATE_PRELIGHT:
            self.style_red.fg[s] = red
            self.style_yellow.fg[s] = yellow

        self.button = {}
        for mailbox in mailboxes:
            b = MyButton(mailbox.name)
            b.connect("clicked",self.click,mailbox)
            self.box.pack_start(b, True, True, 0)
            b.show()
            mailbox.button = b

        self.box.show()
        self.window.show()


        for mailbox in mailboxes:
            threading.Thread(target=self.monitorMailbox,args=(mailbox,)).start()

log(1, "imapnotify version %s" % version)

config = ConfigParser.SafeConfigParser()

config.add_section('Application')
config.set('Application','stick','no')
config.set('Application','desktop','no')
config.set('Application','tooltips','yes')
config.set('Application','showcount','yes')
config.set('Application','decorated','yes')
config.set('Application','keepontop','no')
config.set('Application','keeponbottom','no')
config.set('Application','skiptaskbar','no')
config.set('Application','skippager','no')
config.set('Application','title','IMAP Notifier')

allowedApplicationOptions = [name for name,value in config.items('Application')]
allowedMailboxOptions = ['username','password','server','polltime','boxname','cmd','delayedexpunge','ssl_version','connection_status_only']

config.read(option.configfile)

for name,value in config.items('Application'):
    if name not in allowedApplicationOptions:
        print "Unrecognized Application option: '%s'" % name
        sys.exit(1)

tooltipsEnabled = config.getboolean('Application','tooltips')
showcountEnabled = config.getboolean('Application','showcount')

mailboxes = []

# want to preserve mailbox ordering based on section ordering in
# config file, so re-read config file to get mailbox names in order

for line in open(option.configfile):
    line = line.strip()
    if line.startswith('[') and line.endswith(']'):
        secname = line[1:-1]
        if secname != 'Application':
            m = Mailbox(secname)
            for name,value in config.items(secname):
                if name not in allowedMailboxOptions:
                    print "Unrecognized Mailbox [%s] option: '%s'" % (secname,name)
                    sys.exit(1)
                if name == 'polltime':
                    value = int(value)
                elif name == 'cmd':
                    value = shlex.split(value)
                m.__dict__[name] = value
            # convert ssl version from string to constant from ssl module
            if m.ssl_version:
                if not ssl.__dict__.has_key(m.ssl_version):
                    print "Unrecognized ssl_version value: '%s'" % m.ssl_version
                    sys.exit(1)
                m.ssl_version = ssl.__dict__[m.ssl_version]
            if m.connection_status_only is not None:
                m.connection_status_only = config.getboolean(m.name,'connection_status_only')
            mailboxes.append(m)

notifier = Notifier(mailboxes)

try:
    gtk.main()
except KeyboardInterrupt:
    pass

notifier.shutdown()
try:
    gtk.main_quit()
except:
    pass
        
