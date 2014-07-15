imapnotify
==========

GTK based IMAP mailbox notification application

Imapnotify is an email notification agent written in Python using
pyGTK and imaplib2.py (with some local changes that have been
submitted upstream).  As the name implies, it only works with IMAP
servers.  It doesn't do POP, mbox, maildir, mh, or anything else.

It is a bit of a memory hog on the surface.  On the author's computer
monitoring 4 mailboxes, imapnotify as a resident set size of 16MB and
a virtual set size of 169M.  9MB is shared with other applications
that are using Python and/or Gtk, so in practical terms it's only
reponsible for 7MB of physical RAM usage, so it's not all that bad.

Imapnotify uses the IMAP idle command which allows the IMAP server to
"push" notification to the client immediately upon arrival of new mail
(or deletion of messages).  This has two advantages:

  1. Much lower CPU usage compared to notifiers such as XFCE's
     mailwatch panel plugin which opens a new connection for each
     poll.  If SSL encyryption is being used, there is a significant
     amount of overhead involved in setting up a connection that is
     then only used to send a single command.

  2. Lower latency notification.  The user is notified within seconds
     of new mail being received.

The Imapnotify UI consists of a vertical array of GTK buttons whose
labels change color from black to red when new mail is present in the
associated mailbox.  Labels will be yellow whever imapnotify isn't
logged in with the specified mailbox successfully selected.  It can
also be configured to show the number of unseen messages as tooltips
and/or directly in the button labels.

Imapnotify can be configured to monitor any number of mailboxes on any
number of servers.

Each button in the UI can be configured to run a shell command when
clicked.  Assuming the shell command is used to start a MUA,
imapnotify will recheck the mailbox status after the shell command
terminates.

Configuration is done through a config file and command-line options.

Command line Options
--------------------

The available command line options are shown below

    -h, --help                          show this help message and exit
    -l FILE, --log=FILE                 write log to FILE
    -v LEVEL, --verbose=LEVEL           verbosity level
    -g GEOMETRY, --geometry=GEOMETRY    X11 geometry string
    -f FILE, --config-file=FILE         use FILE instead of ~/.imapnotifyrc

On startup, imapnotify will attempt to read a config file from
$HOME/.imapnotifyrc or from the path specified with the
-f/--config-file option.

Config File
-----------

The config file is parsed using the Python standard library's
configparser module:

 http://docs.python.org/release/2.6.6/library/configparser.html

A section header of Application identifies application-wide
settings.  

### Global Application Settings

 * tooltips

   If set to 'yes', the buttons will have tooltips that show how
   many unseen messages are present.  Default is 'yes'.

 * showcount

   If set to 'yes', the buttons will show the number of unseen
   messages in the button labels (when non-zero).  Default is 'yes'.

 * stick         

   If set to 'yes', the imapnotify window will stick to it's
   place on the root window even when virtual desktops are
   changed.  Default is 'no'.

 * decorated

   If set to 'yes', the window manager hints will be set to
   allow normal window decorations (borders, buttons, etc.).
   Default is 'yes'.

 * keepontop

   If set to 'yes', the imapnotify window will be configured
   to stay on top of all other application windows.  Default is
   'no'.

 * keeponbottom

   If set to 'yes', the imapnotify window will be configured
   to stay on top of all other application windows.  Default is
  'no'.

 * desktop
 
   If set to 'yes', the imapnotify window type hint will be set
   to 'desktop'.  I'm not really sure what that does, but maybe
   somebody has a use for it.  Default is 'no'

 * skiptaskbar

   If set to 'yes', the imapnotify window will not appear in
   desktop manager taskbars.  Default is 'no'.

  * skippager

    If set to 'yes', the imapnotify window will not appear in
    desktop manager pagers.  Default is 'no'.

  * title

    The imapnotify window title.  Default is 'IMAP Notifier'.


### Mailbox Configuration Settings

Any section with a name other than Application defines a mailbox
configuration.  The UI button will have the same name as the section,
and the buttons will appear in the same order as the configuration
sections in the config file. Mailbox configuration settings are as
follows:

 * server

   The IMAP server.

 * username

   The username to use when logging into the IMAP server.

 * password

   The password to use when logging into the IMAP server.

 * boxname

   The mailbox name to watch for new mail

 * polltime

   The polling period to use if the IMAP server doesn't support push
   notification via the "idle" command.

 * cmd

   The shell command to execute when the button is clicked.

 * delayedexpunge

   Set to true if the IMAP server is slow in expunging deleted
   messages.  The issue that this is meant to solve is the case where
   the user clicks a notifier button starting an MUA, reads or deletes
   new messages, and exits.  Imapnotify will re-check the mailbox
   status when the MUA exits.  On some servers, the status won't
   change immediately and imapnotify will still see "new" mail that
   has just been deleted or marked read.  Setting delayedexpunge will
   cause imapnotify to delay for a short while before re-checking the
   mailbox status after the MUA exits.

 * ssl_version

   If set to one of the PROTOCOL_xxx values from the ssl module, this
   value will be passed to ssl.wrap_socket() call.

 * connection_status_only

   If set to 1/on/true the button will not change color/label based on
   unseen messages -- button will stay black unless connection fails
   at which time it will turn yellow (as usual).

Here is a sample .imapnotifyrc file that defines two mailboxes to be
monitored:

### Example Configuration

    [Application]
    stick = yes
    keepontop = yes
    decorated = no
    
    [Panix]
    username = mypanixusername
    password = mypanixpassword
    server = imap.panix.com
    cmd = aterm -T mutt -n 'mutt panix' -ls -e mutt -F ~/.muttrc.panix
    delayedexpunge = yes

    [Gmail]
    username = mygmailuseranme
    password = mygmailpassword
    server = imap.gmail.com
    cmd = aterm -T 'mutt gmail' -n 'mutt gmail' -ls -e mutt -F ~/.muttrc.gmail
