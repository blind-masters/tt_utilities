import wx
import configparser
import webbrowser
import TeamTalk5 as teamtalk
import mpv
import gettext
import os
import wx.lib.scrolledpanel as scrolled


class ConfigWizard(wx.Frame):
    """
    A multi-page wizard to guide the user through the initial configuration process.
    """
    def __init__(self, parent, title, config_structure, gettext_func, init_ui=True):
        super().__init__(parent, title=title, size=(600, 450))
        self.config_structure = config_structure
        self.language = "en"
        self._ = gettext_func
        self.values = {}
        self.controls = {}

        self._group_structure_into_pages()

        self.current_page = 0
        if init_ui:
            self.InitUI()
            self.Centre()
            self.Show()

    def _group_structure_into_pages(self):
        """Groups the flat config structure into pages for the wizard."""
        self.pages = []
        current_page = None
        for item in self.config_structure:
            if item.get('type') == 'header':
                current_page = {"label": item['text'], "fields": []}
                self.pages.append(current_page)
            elif current_page is not None:
                current_page["fields"].append(item)
            else:
                # This case handles if the config structure doesn't start with a header.
                current_page = {"label": "General", "fields": [item]}
                self.pages.append(current_page)

    def InitUI(self):
        self.panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        self.page_label = wx.StaticText(self.panel, label="")
        main_sizer.Add(self.page_label, 0, wx.ALL | wx.CENTER, 10)

        # Use a scrolled panel for the form fields
        self.scrolled_panel = scrolled.ScrolledPanel(self.panel, -1, style=wx.TAB_TRAVERSAL)
        self.fields_sizer = wx.BoxSizer(wx.VERTICAL)
        self.scrolled_panel.SetSizer(self.fields_sizer)
        main_sizer.Add(self.scrolled_panel, 1, wx.EXPAND | wx.ALL, 5)

        # Navigation buttons
        nav_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.back_button = wx.Button(self.panel, label=self._("Back"))
        self.next_button = wx.Button(self.panel, label=self._("Next"))
        self.finish_button = wx.Button(self.panel, label=self._("Finish"))
        nav_sizer.Add(self.back_button, 0, wx.ALL, 5)
        nav_sizer.AddStretchSpacer()
        nav_sizer.Add(self.next_button, 0, wx.ALL, 5)
        nav_sizer.Add(self.finish_button, 0, wx.ALL, 5)
        main_sizer.Add(nav_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.panel.SetSizer(main_sizer)

        self.back_button.Bind(wx.EVT_BUTTON, self.on_back)
        self.next_button.Bind(wx.EVT_BUTTON, self.on_next)
        self.finish_button.Bind(wx.EVT_BUTTON, self.on_finish)

        self.load_page()

    def load_page(self):
        """Loads the controls for the current wizard page."""
        self.fields_sizer.Clear(True)
        page_data = self.pages[self.current_page]

        gettext.bindtextdomain("messages", "locales")
        gettext.textdomain("messages")
        try:
            translation = gettext.translation("messages", "locales", [self.language])
            self._ = translation.gettext
        except FileNotFoundError:
            self._ = gettext.gettext
                
        self.page_label.SetLabel(self._(page_data['label']))
        self.back_button.SetLabel(self._("Back"))
        self.next_button.SetLabel(self._("Next"))
        self.finish_button.SetLabel(self._("Finish"))

        first_control = None
        for field in page_data['fields']:
            if field.get('type') == 'header':
                continue
            control, label_sizer = self._create_field_control(self.scrolled_panel, field)
            self.fields_sizer.Add(label_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
            if control and not first_control:
                first_control = control

        self.scrolled_panel.SetupScrolling()
        self.panel.Layout()        

        if first_control:
            first_control.SetFocus() # Set focus to the first item

        self.back_button.Enable(self.current_page > 0)
        self.next_button.Show(self.current_page < len(self.pages) - 1)
        self.finish_button.Show(self.current_page == len(self.pages) - 1)

    def on_next(self, event):
        if not self._save_page_values():
            return # Validation failed
        
        if self.current_page == 0:
            key = ('bot', 'language')
            self.language = self.values.get(key, 'en')
                
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.load_page()

    def on_back(self, event):
        self._save_page_values() # Save current state just in case
        if self.current_page > 0:
            self.current_page -= 1
            self.load_page()

    def on_finish(self, event):
        if not self._save_page_values():
            return
        self._save_config_file()
        self.Close()

    def _save_page_values(self):
        """Reads values from the current page's controls into self.values."""
        page_data = self.pages[self.current_page]
        for field in page_data['fields']:
            if 'section' not in field or 'key' not in field:
                continue
                
            unique_key = (field['section'], field['key'])
            control = self.controls.get(unique_key)
            if not control: continue

            if field['type'] == 'bool':
                self.values[unique_key] = control.GetValue()
            elif field['type'] == 'radio':
                self.values[unique_key] = control.GetStringSelection()
            elif field['type'] in ('text', 'password', 'int'):
                val_str = control.GetValue()
                if field.get('required') and not val_str:
                    wx.MessageBox(self._("'{}' is a required field.").format(self._(field['prompt'])), self._("Input Error"), wx.OK | wx.ICON_ERROR)
                    control.SetFocus()
                    return False
                self.values[unique_key] = val_str
            elif field['type'] in ('device', 'language'):
                self.values[unique_key] = control.GetClientData(control.GetSelection())
            elif field['type'] == 'choice':
                selection_index = control.GetSelection()
                if selection_index != wx.NOT_FOUND:
                    original_key_str = list(field['options'].keys())[selection_index]
                    self.values[unique_key] = field['options'][original_key_str]

        return True

    def _save_config_file(self):
        """Writes all collected values to config.ini."""
        config = configparser.ConfigParser()
        for field in self.config_structure:
            if 'section' not in field or 'key' not in field:
                continue
            section, key = field['section'], field['key']
            unique_key = (section, key)
            value = self.values.get(unique_key, field.get('default', ''))

            if not config.has_section(section):
                config.add_section(section)
            
            config.set(section, key, str(value))

        with open("config.ini", "w", encoding="utf-8") as configfile:
            config.write(configfile)
        wx.MessageBox(self._("Configuration saved successfully to config.ini!"), self._("Success"), wx.OK | wx.ICON_INFORMATION)

    def _create_field_control(self, parent, field):
        """Dynamically creates a wx control based on the field definition."""
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        control = None
        field_type = field['type']
        
        if 'section' not in field or 'key' not in field:
            # Handle non-standard fields like headers if necessary
            return None, sizer

        unique_key = (field['section'], field['key'])
        default = field.get('default', '')

        if field_type == 'bool':
            control = wx.CheckBox(parent, label=self._(field['prompt']))
            control.SetValue(default is True)
            sizer.AddStretchSpacer(1) 
            sizer.Add(control, 2, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        else:
            label = wx.StaticText(parent, label=self._(field['prompt']) + ":", style=wx.ALIGN_RIGHT)
            sizer.Add(label, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

            if field_type in ('text', 'int'):
                control = wx.TextCtrl(parent, value=str(default))
            elif field_type == 'password':
                control = wx.TextCtrl(parent, value=str(default), style=wx.TE_PASSWORD)
            elif field_type == 'choice':
                options = [self._(opt) for opt in field['options'].keys()]
                control = wx.Choice(parent, choices=options)
                if default in field['options']:
                    control.SetStringSelection(self._(default))
            elif field_type == 'language':
                control = wx.ComboBox(parent, style=wx.CB_READONLY)
                self._populate_languages(control)
            elif field_type == 'device':
                control = wx.ComboBox(parent, style=wx.CB_READONLY)
                if field['device_type'] == 'input': self._populate_input_devices(control)
                else: self._populate_output_devices(control)

            if control:
                sizer.Add(control, 2, wx.EXPAND | wx.ALL, 5)

        if control:
            self.controls[unique_key] = control
        return control, sizer

    def _populate_languages(self, combo):
        locales_dir = "locales"
        if os.path.exists(locales_dir):
            langs = [d for d in os.listdir(locales_dir) if os.path.isdir(os.path.join(locales_dir, d))]
            for lang in sorted(langs):
                combo.Append(lang, lang)
        combo.SetStringSelection(self.language)

    def _populate_input_devices(self, combo):
        try:
            tt = teamtalk.TeamTalk(); devices = tt.getSoundDevices(); tt.closeTeamTalk()
            for dev in devices:
                if dev.nMaxInputChannels > 0:
                    combo.Append(teamtalk.ttstr(dev.szDeviceName), dev.nDeviceID)
            if combo.GetCount() > 0: combo.SetSelection(0)
        except Exception: pass

    def _populate_output_devices(self, combo):
        try:
            player = mpv.MPV(vo='null', video=False); devices = player.audio_device_list; player.terminate()
            for i, dev in enumerate(devices):
                combo.Append(dev['description'], i)
            if combo.GetCount() > 0: combo.SetSelection(0)
        except Exception: pass


class MissingConfigDialog(wx.Dialog):
    """
    A dialog that prompts the user to fill in only the missing configuration values.
    """
    def __init__(self, parent, title, missing_items, config_file):
        super().__init__(parent, title=title, size=(500, 350))
        self.missing_items = missing_items
        self.config_file = config_file
        self.controls = {}
        self._ = gettext.gettext # Assuming language is already set
        self.InitUI()
        self.Centre()
        self.ShowModal()

    def InitUI(self):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        info_text = wx.StaticText(panel, label=self._("Your config.ini is missing some settings. Please provide them below."))
        main_sizer.Add(info_text, 0, wx.ALL, 10)

        scrolled_panel = scrolled.ScrolledPanel(panel, -1, style=wx.TAB_TRAVERSAL)
        fields_sizer = wx.BoxSizer(wx.VERTICAL)
        
        temp_wizard = ConfigWizard(None, "", [], self._, init_ui=False)
        for item in self.missing_items:
            if 'key' not in item: continue
            control, label_sizer = temp_wizard._create_field_control(scrolled_panel, item)
            fields_sizer.Add(label_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        
        self.controls = temp_wizard.controls
        temp_wizard.Destroy()

        scrolled_panel.SetSizer(fields_sizer)
        scrolled_panel.SetupScrolling()
        main_sizer.Add(scrolled_panel, 1, wx.EXPAND | wx.ALL, 5)

        btn_sizer = wx.StdDialogButtonSizer()
        save_btn = wx.Button(panel, wx.ID_SAVE, self._("Save"))
        cancel_btn = wx.Button(panel, wx.ID_CANCEL)
        btn_sizer.AddButton(save_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        panel.SetSizer(main_sizer)
        self.Fit()
        save_btn.Bind(wx.EVT_BUTTON, self.on_save)

    def on_save(self, event):
        """Saves the entered values to the existing config file."""
        config = configparser.ConfigParser()
        config.read(self.config_file)

        values = {}
        for item in self.missing_items:
            unique_key = (item['section'], item['key'])
            control = self.controls.get(unique_key)
            if not control: continue

            if item['type'] == 'bool':
                values[unique_key] = control.GetValue()
            elif item['type'] in ('text', 'password', 'int'):
                val_str = control.GetValue()
                if item.get('required') and not val_str:
                    wx.MessageBox(self._("'{}' is a required field.").format(self._(item['prompt'])), self._("Input Error"), wx.OK | wx.ICON_ERROR)
                    control.SetFocus()
                    return
                values[unique_key] = val_str
            elif item['type'] in ('device', 'language'):
                values[unique_key] = control.GetClientData(control.GetSelection())
            elif item['type'] == 'choice':
                selection_index = control.GetSelection()
                if selection_index != wx.NOT_FOUND:
                    original_key_str = list(item['options'].keys())[selection_index]
                    values[unique_key] = item['options'][original_key_str]
                
        for item in self.missing_items:
            section, key = item['section'], item['key']
            unique_key = (section, key)
            value = values.get(unique_key)
            if value is not None:
                if not config.has_section(section):
                    config.add_section(section)
                config.set(section, key, str(value))
        
        with open(self.config_file, "w", encoding="utf-8") as f:
            config.write(f)
        
        wx.MessageBox(self._("Configuration updated successfully! The bot will now continue."), self._("Success"), wx.OK | wx.ICON_INFORMATION)
        self.EndModal(wx.ID_OK)