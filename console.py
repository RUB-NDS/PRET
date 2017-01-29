import sys, json, curses
import npyscreen

class SearchDropdown(npyscreen.fmForm.Form):
    DEFAULT_LINES = 7
    DEFAULT_COLUMNS = 40
    SHOW_ATX = 33
    SHOW_ATY = 3

class FilterDropdown(npyscreen.fmForm.Form):
    DEFAULT_LINES = 19
    DEFAULT_COLUMNS = 17
    SHOW_ATX = 33
    SHOW_ATY = 4

class HelpMessage(npyscreen.fmForm.Form):
    DEFAULT_LINES = 9
    DEFAULT_COLUMNS = 45
    SHOW_ATX = 33
    SHOW_ATY = 4

class FilterButton(npyscreen.MiniButtonPress):

    def whenPressed(self):
        self.parent.parentApp.mainform.filter()

    def h_exit_down(self, null):
        self.parent.parentApp.mainform.name = 'Dictionary Browser'
        super(FilterButton, self).h_exit_down(null)

    h_exit_mouse = h_exit_down

class SearchButton(npyscreen.MiniButtonPress):

    def whenPressed(self):
        self.parent.parentApp.mainform.search()

class DictList(npyscreen.MLTree):

    def filter_value(self, index):
        return self._filter in ''.join(self._get_content(self.display_value(self.values[index])).values())

    def update(self, clear = False):
        try:
            self.h_select(self)
            super(DictList, self).update()
            c = self.values[self.cursor_line].get_content()
            self.parent.parentApp.mainform.update_value(c['value'], c['type'], c['perms'])
            self.parent.parentApp.mainform.update_perms(c['perms'])
        except:
            pass

    def set_up_handlers(self):
        super(npyscreen.MLTree, self).set_up_handlers()
        self.handlers.update({ord('<'): self.h_collapse_tree,
         ord('>'): self.h_expand_tree,
         ord('{'): self.h_collapse_all,
         ord('}'): self.h_expand_all})


class Dict(npyscreen.BoxTitle):
    _contained_widget = DictList


class Perms(npyscreen.BoxTitle):
    _contained_widget = npyscreen.MultiSelect


class ValueEdit(npyscreen.MultiLineEdit):

    def adjust_widgets(self):
        self.color = 'DANGER'
        print 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'


class Value(npyscreen.BoxTitle):
    _contained_widget = ValueEdit


class TreeDataDump(npyscreen.TreeData):

    def get_content_for_display(self):
        return str(self.content['key'] + ': ' + self.content['value'])


class Browser(npyscreen.NPSAppManaged):

    def onStart(self):
        self.mainform = self.addForm('MAIN', MainForm)

    def set_data(self, name, data):
        self.name = name
        self.data = data

    def get_data(self):
        treedata = TreeDataDump(content=self.name)
        self.populate(treedata, self.data)
        return treedata

    def populate(self, treedata, data):
        try:
            if self.mainform.filter_text.value:
                filter = self.mainform.filter_text.value + 'type'
            else:
                filter = ''
        except AttributeError:
            filter = ''

        if isinstance(data, dict):
            for key, val in data.items():
                recursion = False
                type = val['type']
                perms = val['perms']
                value = val['value']
                if isinstance(value, dict):
                    value, recursion = '', True
                if isinstance(value, list):
                    try:
                        value = ' '.join((x['value'] for x in value))
                    except:
                        value, recursion = '', True

                c = {'key': key,
                 'value': value,
                 'type': type,
                 'perms': perms}
                if not filter or type == filter or recursion:
                    c1 = treedata.new_child(content=c)
                    if recursion:
                        self.populate(c1, val['value'])

        if isinstance(data, list):
            count = 0
            for val in data:
                count = count + 1
                key = str(count)
                recursion = False
                type = val['type']
                perms = val['perms']
                value = val['value']
                if isinstance(value, dict):
                    value, recursion = '', True
                if isinstance(value, list):
                    try:
                        value = ' '.join((x['value'] for x in value))
                    except:
                        value, recursion = '', True

                c = {'key': key,
                 'value': value,
                 'type': type,
                 'perms': perms}
                if not filter or type == filter or recursion:
                    c1 = treedata.new_child(content=c)
                    if recursion:
                        self.populate(c1, val['value'])


class MainForm(npyscreen.FormBaseNew):

    def quit(self, *args):
        exit()

    def update_dict(self):
        self.dict.values = self.parentApp.get_data()
        self.dict.display()
        self.dict.entry_widget.reset_cursor()
        self.items.value = len(self.dict.values)

    def update_perms(self, perms):
        self.perms.values = ['read', 'write', 'execute']
        self.perms.value = []
        if 'r' in perms:
            self.perms.value += [0]
        if 'w' in perms:
            self.perms.value += [1]
        if 'x' in perms:
            self.perms.value += [2]
        self.perms.display()

    def update_value(self, value, type, perms):
        self.value.name = 'Edit Value (' + type + ')'
        self.value.value = value
        if 'w' in perms:
            self.value.editable = True
        else:
            self.value.editable = False
        self.value.display()

    def adjust_widgets1(self):
        self.dict.entry_widget._filter = self.searchline.value
        filtered_lines = self.dict.entry_widget.get_filtered_indexes()
        len_f = len(filtered_lines)
        if not self.searchline.value:
            self.statusline.value = ''
        elif len_f == 0:
            self.statusline.value = '(No Matches)'
        elif len_f == 1:
            self.statusline.value = '(1 Match)'
        else:
            self.statusline.value = '(%s Matches)' % len_f
        self.statusline.display()

    def search(self, *args):
        self.dict._contained_widget.h_set_filter
        self.dict.entry_widget.h_set_filter
        window = SearchDropdown(name='by key/value')
        self.searchline = window.add(npyscreen.TitleText, name='Keyword:', value=self.search_text.value)
        window.nextrely += 1
        self.statusline = window.add(npyscreen.Textfield, color='LABEL', editable=False)
        window.adjust_widgets = self.adjust_widgets1
        window.display()
        self.searchline.edit()
        self.dict.entry_widget._remake_filter_cache()
        self.dict.entry_widget.jump_to_first_filtered()
        self.search_btn.h_exit_down(ord('a'))
        self.filter_btn.h_exit_down(ord('a'))
        self.search_text.value = self.searchline.value
        self.search_text.update()

    def filter(self, *args):
        window = FilterDropdown(name='by datatype')
        select = window.add_widget(npyscreen.MultiLine, return_exit=True, select_exit=True, values=['name',
         'string',
         'boolean',
         'integer',
         'real',
         'null',
         'operator',
         'dict',
         'array',
         'packedarray',
         'file',
         'font',
         'gstate',
         'mark',
         'save'])
        window.display()
        select.edit()
        if select.value:
            self.filter_text.value = select.values[select.value]
            self.filter_text.update()
            self.update_dict()

    def reset(self, *args):
        self.filter_text.value = ''
        self.search_text.value = ''
        self.filter_text.update()
        self.search_text.update()

    def usage(self, *args):
        message = '  < or >:     collapse/expand node\n  { or }:     collapse/expand tree\n  /:          set search filter\n  f:          set datatype filter\n  r:          reset all filters\n  n:          move next filtered\n  p:          move prev filtered\n  q:          quit application'
        npyscreen.notify_confirm(message, title='Usage Help')

    def commit(self, *args):
        pass

    def create(self):
        self.name = 'Dictionary Browser \xe2\x94\x80\xe2\x94\x80 (Press F1 for help)'
        self.add_handlers({curses.KEY_F1: self.usage,
         ord('/'): self.search,
         ord('f'): self.filter,
         ord('r'): self.reset,
         ord('q'): self.quit})
        self.items = self.add(npyscreen.TitleText, name='Items total', value='0', editable=False)
        self.add(npyscreen.TitleText, name='PS version', value='3010', editable=False)
        self.search_btn = self.add(SearchButton, relx=33, rely=2, name='Search')
        self.search_text = self.add(npyscreen.FixedText, relx=53, rely=2, editable=False)
        self.filter_btn = self.add(FilterButton, relx=33, rely=3, name='Filter')
        self.filter_text = self.add(npyscreen.FixedText, relx=53, rely=3, editable=False)
        self.dict = self.add(Dict, name='Dictionary', scroll_exit=True, max_width=43, relx=2, rely=5, max_height=-2)
        self.perms = self.add(Perms, name='Permissions', scroll_exit=True, rely=5, relx=46, max_height=6)
        self.value = self.add(Value, name='Edit Value', scroll_exit=True, rely=11, relx=46, max_height=-2)
        self.status = self.add(npyscreen.TitleText, name='Status', editable=False, value='Connected to laserjet.lan', rely=-3)
        self.save = self.add(npyscreen.ButtonPress, name='Save Changes', rely=-3, relx=-27)
        self.exit = self.add(npyscreen.ButtonPress, name='Exit', rely=-3, relx=-12)
        self.save.whenPressed = self.commit
        self.exit.whenPressed = self.quit
        self.update_dict()
