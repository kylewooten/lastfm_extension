# -*- Mode: python; coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
#
# Copyright (C) 2012 - Carrasco Agustin
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301  USA.

import pylast
from abc import ABCMeta, abstractproperty
from gi.repository import GObject, Gio, Gtk, Peas, RB

import rb
from ConfigParser import SafeConfigParser
import imp

try:
    import LastFMExtensionFingerprinter
    from LastFMExtensionFingerprinter import LastFMFingerprinter as Fingerprinter
except Exception as e:
    Fingerprinter = e

import LastFMExtensionKeys as Keys
import LastFMExtensionUtils
import LastFMExtensionGui as GUI
from LastFMExtensionUtils import asynchronous_call as async, notify
from LastFMExtensionGui import ConfigDialog

import gettext
gettext.install( 'rhythmbox', RB.locale_dir(), unicode=True )

ui_str = """
<ui>
  <toolbar name="ToolBar">
    <placeholder name="PluginPlaceholder">
      <toolitem name="Loves" action="LoveTrack"/>
      <toolitem name="Ban" action="BanTrack"/>
    </placeholder>
  </toolbar>
</ui>
"""

LASTFM_ICON = 'img/as.png'
LOVE_ICON = 'img/love.png'
BAN_ICON = 'img/ban.png'

#Extensions configuration file
EXT_CONFIG = 'extensions.conf'
#Extensions module's prefix
EXT_PREFIX = 'LastFMExtension'

'''
Base class for all the extensions managed by this plugin.
'''
class LastFMExtension( object ):
    __metaclass__ = ABCMeta

    '''
    By default, all extension are initialized allocating a 'settings' attribute
    that points to a Gio.Settings object binded to the global settings of the
    plugin. Each extension can make use of it to check or modify it's settings.
    '''
    def __init__( self, plugin ):
        self.settings = plugin.settings
        self.initialised = False

        if plugin.connected and self.enabled:
            self.initialise( plugin )

        self.conn_id = self.settings.connect( 'changed::%s' % Keys.CONNECTED,
                                              self.connection_changed, plugin )
        self.sett_id = self.settings.connect( 'changed::%s' % Keys.EXTENSIONS,
                                              self.settings_changed, plugin )

    '''
    This method should be called ALWAYS before the deletion of the object or
    the deactivation of the plugin. It makes sure that all the resources this
    extensions has taken up are freed.
    '''
    def destroy( self, plugin ):
        if self.initialised:
            self.dismantle( plugin )

        self.settings.disconnect( self.conn_id )
        self.settings.disconnect( self.sett_id )

        del self.settings
        del self.conn_id
        del self.sett_id

    '''
    Callback for changes in the connection of the plugin. It ensures that the
    extension is reenabled (if enabled in the first place) when a connection is
    made and to dismantle the plugin (if initialized) when the connection is
    closed.
    '''
    def connection_changed( self, plugin ):
        if not plugin.connected:
            if self.initialised:
                self.dismantle( plugin )

        elif self.enabled:
            self.initialise( plugin )

    '''
    Returns the extensions settings saved on the Gio schema, if such settings
    exist. Otherwise, create a temp one with default values.
    '''
    def _get_ext_settings( self ):
        global_settings = self.settings[Keys.EXTENSIONS]

        try:
            ext_settings = global_settings[self.extension_name]
        except KeyError:
            ext_settings = {'enabled':False}

        return ext_settings

    '''
    Indicates if the extension is enabled. Also allows to enable/disable the
    extension.
    '''
    @property
    def enabled( self ):
        ext_settings = self._get_ext_settings()

        return ext_settings['enabled']

    @enabled.setter
    def enabled( self, enable ):
        ext_settings = self._get_ext_settings()
        ext_settings['enabled'] = enable

        global_settings = self.settings[Keys.EXTENSIONS]
        global_settings[self.extension_name] = ext_settings
        self.settings[Keys.EXTENSIONS] = global_settings

    '''
    Returns the extension name. Read only property.
    '''
    @abstractproperty
    def extension_name( self ):
        pass

    '''
    Returns a description for the extensions. Read only property.
    '''
    @abstractproperty
    def extension_desc( self ):
        pass

    '''
    Returns the ui_str that defines this plugins ui elements to be added to
    Rhythmbox application window. Read only property.
    '''
    @property
    def ui_str( self ):
        pass

    '''
    Initialises the extension. This initialiser should ALWAYS be called by the
    class' subclasses that overrides it, since it haves an initialising sequence
    all extensions should follow.

    Parameters:
        plugin -- the current instance of the plugin managed by Rhythmbox.
    '''
    def initialise( self, plugin ):
        self.create_actions( plugin )
        self.create_ui( plugin )
        self.connect_signals( plugin )

        self.network = plugin.network
        self.initialised = True

    '''
    Dismantles the extension when it's disabled. This destroy any ui, signa-
    handlers and actions the extension may have created during it's initializa-
    tion.

    Parameters:
        plugin -- the current instance of the plugin managed by Rhythmbox.
    '''
    def dismantle( self, plugin ):
        self.disconnect_signals( plugin )
        self.destroy_ui( plugin )
        self.destroy_actions( plugin )

        self.initialised = False

    '''
    Creates all the extension's related actions and inserts them into the
    application.
    This method is always called when the extension is initialised.
    '''
    def create_actions( self, plugin ):
        pass

    '''
    Creates the plugin ui within the Rhythmbox application.
    This method is always called when the extension is initialized
    '''
    def create_ui( self, plugin ):        
        if self.ui_str != None:
            self.ui_id = plugin.uim.add_ui_from_string( self.ui_str )

    '''
    Connects all the extension's needed signals for it to function correctly.
    This method is always called when the extension is initialized.
    '''
    def connect_signals( self, plugin ):
        pass

    '''
    Disconnects all the signals connected by the extension.
    This method is always called when the extension is dismantled.
    '''
    def disconnect_signals( self, plugin ):
        pass

    '''
    Destroys the extension's ui whithin the Rhythmbox application.
    This method is always called when the extension is dismantled.
    '''
    def destroy_ui( self, plugin ):
        if self.ui_str != None:
            plugin.uim.remove_ui( self.ui_id )
            del self.ui_id

    '''
    Dismantles all the actions created by this extension and dissasociates them
    from the Rhythmbox application.
    This method is always called when the extension is dismantled.
    '''
    def destroy_actions( self, plugin ):
        pass

    '''
    Returns a GTK widget to be used as a configuration interface for the
    extension on the plugin's preferences dialog. Every extension is responsible
    of connecting the correspondent signals and managing them to configure
    itself. By default, this methods returns a checkbox that allows the user
    to enable/disable the extension.
    '''
    def get_configuration_widget( self ):
        def toggled_callback( checkbox ):
            self.enabled = checkbox.get_active()

        widget = Gtk.CheckButton( "Activate %s " % self )
        widget.connect( 'toggled', toggled_callback )
        widget.set_tooltip_text( self.extension_desc )

        return widget

    '''
    Callback for when a setting is changed. The default implementation makes
    sure to initialise or dismantle the extension acordingly.
    '''
    def settings_changed( self, settings, key, plugin ):
        enabled = settings[key][self.extension_name]['enabled']

        if enabled:
            if plugin.connected:
                self.initialise( plugin )

        elif self.initialised:
            self.dismantle( plugin )

    def __str__( self, *args, **kwargs ):
        return self.extension_name

'''
Base class for the extensions that want to use the current track in their 
activity. It automatically connects the playing-changed signal and implements
an utility method to get the current track data.
'''
class LastFMExtensionWithPlayer( LastFMExtension ):
    '''
    Initialises the plugin, saving the shell player on self.player
    '''
    def __init__( self, plugin ):
        self.player = plugin.shell.props.shell_player

        super( LastFMExtensionWithPlayer, self ).__init__( plugin )

    '''
    Connects the playing-changed signal to the callback playing_changed.
    '''
    def connect_signals( self, plugin ):
        super( LastFMExtensionWithPlayer, self ).connect_signals( plugin )

        #connect to the playing change signal
        self.playing_changed_id = self.player.connect( 'playing-changed',
                                                 self.playing_changed, plugin )

    '''
    Disconnects the playing-changed signal.
    '''
    def disconnect_signals( self, plugin ):
        super( LastFMExtensionWithPlayer, self ).disconnect_signals( plugin )

        #disconnect signals
        self.player.disconnect( self.playing_changed_id )

        #delete variables
        del self.playing_changed_id

    '''
    Callback for the playing-changed signal. Subclasses should probably 
    override this method to do whatever they want with it.
    '''
    def playing_changed( self, shell_player, playing, plugin ):
        pass

    '''
    Utility method that gaves easy access to the current playing track.
    It returns the current entry and a pylast Track instance pointing at
    the given track.
    '''
    def get_current_track( self ):
        entry = self.player.get_playing_entry()

        if not entry:
            return ( None, None )

        title = unicode( entry.get_string( RB.RhythmDBPropType.TITLE ),
                         'utf-8' )
        artist = unicode( entry.get_string( RB.RhythmDBPropType.ARTIST ),
                          'utf-8' )

        return ( entry, self.network.get_track( artist, title ) )

'''
This class serves as intermediary between the Plugin and it's Configurable, so
both can access the loaded extensions.
'''
class LastFMExtensionBag( object ):
    instance = None

    def __init__( self, plugin ):
        self.extensions = {}

        #generate config parser
        config_file = rb.find_plugin_file( plugin, EXT_CONFIG )
        parser = SafeConfigParser()
        parser.read( config_file )

        #read the extensions configs
        for extension in parser.sections():
            if parser.getboolean( extension, 'allow' ):
                #if allowed, load the module
                module_name = EXT_PREFIX + extension
                fp, path, desc = imp.find_module( module_name )

                try:
                    module = imp.load_module( module_name, fp, path, desc )

                    #and create an instance of the extension
                    ext_class = getattr( module, 'Extension' )

                    if ext_class:
                        self.extensions[extension] = ext_class( plugin )

                finally:
                    if fp:
                        fp.close()

    def destroy( self, plugin ):
        #destroy all the extensions
        for extension in self.extensions.itervalues():
            extension.destroy( plugin )

    @classmethod
    def initialise_instance( cls, plugin ):
        cls.instance = LastFMExtensionBag( plugin )

    @classmethod
    def destroy_instance( cls, plugin ):
        cls.instance.destroy( plugin )

    @classmethod
    def get_instance( cls ):

        return cls.instance

class LastFMExtensionPlugin ( GObject.Object, Peas.Activatable ):
    __gtype_name = 'LastFMExtensionPlugin'
    object = GObject.property( type=GObject.Object )

    def __init__( self ):
        GObject.Object.__init__( self )
        self.settings = Gio.Settings.new( Keys.PATH )

    @property
    def connected( self ):
        def fget( self ):
            return self.settings['connected']

        def fset( self, connect ):
            self.settings['connected'] = connect

        return locals()

    def do_activate( self ):

        #=======================================================================
        # TODO: Before going to the extensions, the plugin should
        #       - Connect the settings
        #       - Create a network if it's connected, and from there 
        #
        #       The enabling proccess goes like this:
        #       - Iterate over all the extensions names
        #         - Create an instance of the extension
        #         - Initialise the extensions that ARE ENABLED
        #         - Connect a signal to it's settings key to a generic function
        #           that calls 'dismantle' when disabled or 'initialise' when
        #           enabled
        #       The disabling process goes like this:
        #       - Iterate over all the extensions names
        #         - Call dismantle on all enabled extensions
        #         - Disconnect the signals to enable/disable the plugin
        #         - Delete the instance of the extension
        #=======================================================================

        #obtenemos el shell y el player
        shell = self.object
        player = shell.props.shell_player

        #inicializamos el modulo de notificacion
        LastFMExtensionUtils.init( rb.find_plugin_file( self, LASTFM_ICON ) )

        manager = shell.props.ui_manager

        #guardamos la db como atributo
        self.db = shell.get_property( 'db' )

        #guardamos el player en una variable para tenerla mas a mano
        self.player = player

        #conectamos la señal para conectar o desconectar
        self.settings.connect( 'changed::%s' % Keys.CONNECTED,
                                self.conection_changed, manager )
        
        #conectamos una señal con la setting de loved para activar/desactivar
        #la funcionalidad cuando sea necesario
        self.settings.connect( 'changed::%s' % Keys.LOVED, self.connect_loved )

        #conectamos la señal del fingerprinter para activarlo/desactivarlo
        self.settings.connect( 'changed::%s' % Keys.FINGERPRINTER,
                                        self.activate_fingerprinter, manager )

        #inicializamos la network si estan los datos disponibles
        self.conection_changed( self.settings, Keys.CONNECTED, manager )

        #TEST ONLY - REMOVE LATER
        self.shell = self.object
        self.uim = self.object.props.ui_manager
        LastFMExtensionBag.initialise_instance( self )

    def do_deactivate( self ):
        shell = self.object

        #variables que pueden no estar inicializadas
        try:
            self.ui_cm
        except:
            self.ui_cm = None

        try:
            self.fingerprinter
        except:
            self.fingerprinter = None

        #destruimos la ui
        manager = shell.props.ui_manager

        if self.ui_cm:
            manager.remove_action_group( self.finger_action_group )
            manager.remove_ui( self.ui_cm )

        manager.ensure_update()

        #desconectamos las señales
        if self.loved_id:
            self.player.disconnect( self.loved_id )

        #desasignamos variables
        del self.db
        del self.player
        del self.settings

        #borramos el fingerprinter si existe
        if self.fingerprinter:
            del self.finger_action_group
            del self.fingerprinter

        #borramos la network si existe
        if self.network:
            del self.network

        #TESTING
        LastFMExtensionBag.destroy_instance( self )

        del self.shell
        del self.uim

    def get_track( self ):
        entry = self.player.get_playing_entry()

        if not entry or not self.settings[Keys.CONNECTED]:
            return ( None, None )

        title = unicode( entry.get_string( RB.RhythmDBPropType.TITLE ), 'utf-8' )
        artist = unicode( entry.get_string( RB.RhythmDBPropType.ARTIST ), 'utf-8' )

        return ( entry, self.network.get_track( artist, title ) )

    def connect_loved( self, settings, key ):
        try:
            self.loved_id
        except:
            self.loved_id = None

        #si la opcion esta habilitada, conectamos la señal
        if settings[key] and settings[Keys.CONNECTED]:
            self.loved_id = self.player.connect( 'playing-changed',
                                                 self.loved_updater )
        #sino, quitamos la señal
        elif self.loved_id:
            self.player.disconnect( self.loved_id )

    def loved_updater ( self, sp, playing ):
        if not playing:
            return

        entry, track = self.get_track()

        if not entry or not track:
            return

        #obtenemos el loved asincronamente
        async( track.is_loved, self.update_loved, entry )()

    def update_loved( self, loved, entry ):
        if type( loved ) is bool and loved:
            self.db.entry_set( entry, RB.RhythmDBPropType.RATING, 5 )
            self.db.commit()

    def activate_fingerprinter( self, settings, key, manager ):
        try:
            self.fingerprinter
        except:
            self.fingerprinter = None

        #show error if the module couldn't be loaded
        if settings[key] and isinstance( Fingerprinter, Exception ):
            #this means the lastfp module isn't present
            settings[key] = False
            GUI.show_error_message( Fingerprinter.message )

        #if there's already a fingerprinter, deactivate it
        elif self.fingerprinter:
            manager.remove_action_group( self.finger_action_group )
            manager.remove_ui( self.ui_cm )

            del self.finger_action_group
            del self.ui_cm
            del self.fingerprinter

        #if there isn't a fingerprinter and it's supposed to be, create it
        elif settings[key] and settings[Keys.CONNECTED]:
            #creamos el fingerprinter
            self.fingerprinter = Fingerprinter( self )

            #agregamos la action para el fingerprinter
            self.finger_action_group = Gtk.ActionGroup( 
                                            'LastFMExtensionFingerprinter' )
            action_fingerprint = Gtk.Action( 'FingerprintSong',
                                            _( '_Fingerprint Song' ),
                                            _( "Get this song fingerprinted." ),
                                            None )
            icon = Gio.FileIcon.new( Gio.File.new_for_path( 
                                rb.find_plugin_file( self, LASTFM_ICON ) ) )
            action_fingerprint.set_gicon( icon )

            action_fingerprint.connect( 'activate', self.fingerprint_song )

            self.finger_action_group.add_action( action_fingerprint )
            manager.insert_action_group( self.finger_action_group, -1 )

            #agregamos los menues contextuales
            self.ui_cm = manager.add_ui_from_string( 
                                  LastFMExtensionFingerprinter.ui_context_menu )
        manager.ensure_update()

    def get_selected_songs( self ):
        shell = self.object

        page = shell.props.selected_page
        selected = page.get_entry_view().get_selected_entries()

        return selected

    def fingerprint_song( self, _ ):
        for entry in self.get_selected_songs():
            self.fingerprinter.request_fingerprint( entry )

    def conection_changed( self, settings, key, manager ):
        if settings[key]:
            self.network = pylast.LastFMNetwork( 
                api_key=Keys.API_KEY,
                api_secret=Keys.API_SECRET,
                session_key=settings[Keys.SESSION] )
        else:
            self.network = None

        self.connect_loved( settings, Keys.LOVED )
        self.activate_fingerprinter( settings, Keys.FINGERPRINTER, manager )

