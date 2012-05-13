#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#       moshPyTT is a program to view and edit Tesseract boxfiles.
#
#
#
#       This program is free software; you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation; either version 3 of the License, or
#       (at your option) any later version.
#
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#
#       You should have received a copy of the GNU General Public License
#       along with this program; if not, write to the Free Software
#       Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#       MA 02110-1301, USA.

# check pyGTK version
import pygtk
pygtk.require('2.0')

import gtk
import pango
import codecs
import sys
import os
import shutil
import copy
from datetime import datetime
import optparse

#CONVERT A DIRECTORY OF IMAGES TO A DJVU FILE

def main():
    """Parse any arguments, and start moshPyTT"""

    parser = optparse.OptionParser(usage='Usage: %prog [-i image file]')
    parser.add_option('-i', dest='imageFile', action='store',
                             help='an image with a corresponding boxfile')
    parser.add_option('-d', dest='debug', action='store_true', default=False,
                             help='show debugging information')

    (opts, args) = parser.parse_args()

    MoshPyTT(opts)

# parameters
NAME = 'moshPyTT'
VERSION = '0.2'

MENU = \
    '''<ui>
  <menubar name="MenuBar">
    <menu action="File">
      <menuitem action="Open"/>
      <menuitem action="Save"/>
      <menuitem action="SaveAs"/>
      <menuitem action="Quit"/>
    </menu>
    <menu action="Edit">
      <menuitem action="Undo"/>
      <menuitem action="Redo"/>
      <menuitem action="MergeBoxes"/>
      <menuitem action="SplitBoxes"/>
      <menuitem action="DeleteBoxes"/>
    </menu>
    <menu action="Help">
      <menuitem action="About"/>
      <menuitem action="Shortcuts"/>
    </menu>
  </menubar>
</ui>'''

class TesseractBox:

    text = ''

    left = None
    right = None
    top = None
    bottom = None

    page = None

    italic = False
    uline = False
    bold = False

    valid = False # if the box is valid


    def make_string(self):
        """Constructs a box string from the box object"""
        string = ''
        if self.bold:
            string += "@"
        if self.italic:
            string += "$"
        if self.uline:
            string += "'"

        string +=  '%s %d %d %d %d %d' % (self.text, self.left, self.bottom, self.right, self.top, self.page)

        return string

    def set_text(self, string):
        if type(string) is str or type(string) is unicode:
            self.text = string
        else:
            raise TypeError("Box text must be a string. Received " + str(type(string)))

    def check_numbers(self):
        """Checks the box edges to ensure that the "left" edge is really to the
        left of the "right" edge, and simlar for the top/bottom"""

        if self.left > self.right:
            temp = self.left
            self.left = self.right
            self.right = temp

        if self.top < self.bottom:
            temp = self.top
            self.top = self.bottom
            self.bottom = temp


    def move(self, direction, step=1):
        """Move the box to one side, in the direction given, by step pixels."""

        if direction == 'LEFT':
            self.left -= step
            self.right -= step
        elif direction == 'RIGHT':
            self.left += step
            self.right += step
        elif direction == 'TOP':
            self.top += step
            self.bottom += step
        elif direction == 'BOTTOM':
            self.top += step
            self.bottom += step


    def stretch(self, direction, step=1):
        """Stretch the "direction" side of the box by "step" pixels. Negative
        step values produce shrinkage of the box"""

        if direction == 'LEFT':
            self.left -= step
        elif direction == 'RIGHT':
            self.right += step
        elif direction == 'TOP':
            self.top += step
        elif direction == 'BOTTOM':
            self.bottom -= step
        elif direction == 'ALL':
            self.left -= step
            self.right += step
            self.top += step
            self.bottom -= step

        self.check_numbers()


    def __init__(self, string=None):


        if not string:
            return

        parts = string.split()

        if len(parts) == 6:
            try:

                self.left = int(parts[1])
                self.bottom = int(parts[2])
                self.right = int(parts[3])
                self.top = int(parts[4])

                self.page = int(parts[5])

                self.text = parts[0]

                self.valid = True

            except ValueError: # if the int()s fail, ignore this box, there is something wrong with it
                return

            attributeCounter = 0

            while True:
                #don't add attributes we already have, don't add last char
                if self.text[attributeCounter] == '$' and not self.italic and attributeCounter +1 < len(self.text):
                    attributeCounter += 1
                    self.italic = True
                elif self.text[attributeCounter] == '@' and not self.bold and attributeCounter +1 < len(self.text):
                    attributeCounter += 1
                    self.bold = True
                elif self.text[attributeCounter] == "'" and not self.uline and attributeCounter +1 < len(self.text):
                    attributeCounter += 1
                    self.uline = True

                #only the first 3 chars can be attrs, or maybe less
                if attributeCounter > 2 or attributeCounter+1 >= len(self.text) or self.text[attributeCounter] not in ['@', '$', "'"]:
                    break

            self.text = self.text[attributeCounter:]


class UndoRedoStack:

    def __init__(self):

        self.undoStack = []
        self.redoStack = []


    def undo(self):
        """Grab an item off the stack, if there is one, but leave it in place"""

        if len(self.undoStack) > 0:
            item = self.undoStack.pop() # pop off the undo stack
            self.redoStack.append(item) # and onto the redo stack
            return item
        else: #there is nothing to undo
            return None


    def redo(self):

        if len(self.redoStack) > 0:
            item = self.redoStack.pop() # pop off the redo stack
            self.undoStack.append(item) # and onto the redo stack
            return item
        else: #there is nothing to redo
            return None


    def add_item(self, item):
        self.undoStack.append(item) # add the item to the undo stack
        self.redoStack = [] #invalidate the redo stack


class MoshPyTT:

    pixbuf = None
    newBoxList = None # a temporary list of boxes produced after a merge. If != None, then there are newBoxes to deal with
    deleteBoxes = False
    boxList = [] # a list of boxes that are selected
    blockUndoRedo = False #do not add the next action to the undo/redo stack
    userScrolled = False #true if the user overrides the automatic scrolling
    userSetAttributes = True #true if a toggling of the attribute button means the box needs to be updated
    boxfileChangedSinceSave = False #true if there are unsaved changes
    blockUpdates = False #true to prevent update callback firing
    changeCounter = 0 #counter of changes to the boxfile

    def error_dialog(self, labelText, parent):
        dialog = gtk.Dialog('Error', parent, gtk.DIALOG_NO_SEPARATOR
                            | gtk.DIALOG_MODAL, (gtk.STOCK_OK,
                            gtk.RESPONSE_OK))
        label = gtk.Label(labelText)
        dialog.vbox.pack_start(label, True, True, 0)
        label.show()
        dialog.run()
        dialog.destroy()


    # CALLBACKS
    def on_redraw(self, drawingArea, event):
        self.redraw_drawing_area()


    def on_mark_set(self, textBuffer, iter, textMark):

        cursor = self.textBuffer.get_insert()
        iterAtCursor = self.textBuffer.get_iter_at_mark(cursor)
        cursorLine = iterAtCursor.get_line()

        endLine = self.textBuffer.get_end_iter().get_line()


        vAdj = self.textScroll.get_vadjustment()

        #if the value is above the current page
        value = vAdj.upper * (cursorLine/float(endLine))
        if value < vAdj.value:
            vAdj.value = value

        #if the value is below the current page
        value = vAdj.upper * ((cursorLine+1)/float(endLine))
        if value > vAdj.value + vAdj.page_size:
            vAdj.value  = value - vAdj.page_size

        self.get_current_box()


    def on_buffer_changed(self, event):
        self.get_current_box()


    def on_insert_text(self, textBuffer, startIter, insertedText, length):

        allowUndo = self.on_change()

        if allowUndo:
            offset = startIter.get_offset()
            undoStackItem = {'action':'INS', 'text':insertedText, 'offset':offset}

            self.undoRedoStack.add_item( undoStackItem )


    def on_delete_range(self, textBuffer, startIter, endIter):

        allowUndo = self.on_change()

        if allowUndo:
            deletedText = self.textBuffer.get_text(startIter, endIter)
            offset = startIter.get_offset()
            undoStackItem = {'action':'DEL', 'text':deletedText, 'offset':offset}
            self.undoRedoStack.add_item( undoStackItem )


    def on_change(self):
        """Process actions on a change.
        Return false if the action should NOT be added to the undo/redo stack
        Returns true if it should
        """

        self.boxfileChangedSinceSave = True
        self.changeCounter += 1

        if self.changeCounter >= self.autosaveChangeLimit:
            self.autosave_boxfile()
            self.changeCounter = 0

        if self.blockUndoRedo: #if the action was blocked
            self.blockUndoRedo = False #allow the next one
            return False

        return True


    def on_scroll_image(self, range, scroll, value):
        self.userScrolled = True # the user overrides the image scrolling


    def on_checkbutton_toggled(self, widget, attribute):
        """An attribute checkbutton was toggled"""

        if not self.userSetAttributes:
            return

        value = widget.get_active()

        self.newBoxList = self.boxList #copy the boxlist to prevent a callback messing with it before we use it

        for box in self.newBoxList:
            if attribute == 'BOLD':
                box.bold = value
            elif attribute == 'ITALIC':
                box.italic = value
            elif attribute == 'ULINE':
                box.uline = value

        self.update_boxes()


    def on_find_clicked(self, button, forward=True):
        """One of the find buttons was clicked

        If forward is true, find the next example of the given text, otherwise
        find the previous one
        """

        searchString = self.findEntry.get_text()
        iterAtCursor = self.textBuffer.get_iter_at_mark(self.textBuffer.get_insert())

        while True:
            try:
                if forward:
                    startIter, endIter = iterAtCursor.forward_search(searchString, gtk.TEXT_SEARCH_TEXT_ONLY)
                else:
                    startIter, endIter = iterAtCursor.backward_search(searchString, gtk.TEXT_SEARCH_TEXT_ONLY)
            except TypeError:
                break

            if startIter: #if we found anything

                #if the text is previously selected by this function, move to
                #end of selection and start again
                if startIter.get_offset() == iterAtCursor.get_offset():
                    iterAtCursor = endIter
                    continue

                self.textBuffer.place_cursor(startIter)
                self.textBuffer.move_mark_by_name('selection_bound', endIter)

                break
            else:
                break


    def on_entry_key_press(self, entry, event):

        control = event.state & gtk.gdk.CONTROL_MASK
        shift = event.state & gtk.gdk.SHIFT_MASK
        alt = event.state & gtk.gdk.MOD1_MASK

        command = None
        if control or shift or alt:
            print event.keyval
            if event.keyval in [gtk.keysyms.KP_Left, gtk.keysyms.KP_4, gtk.keysyms._4, gtk.keysyms.Left]: #Left arrow
                command = 'LEFT'

            elif event.keyval in [gtk.keysyms.KP_Up, gtk.keysyms.KP_8, gtk.keysyms._8, gtk.keysyms.Up]:  # Up arrow
                command = 'TOP'

            elif event.keyval in [gtk.keysyms.KP_Right, gtk.keysyms.KP_6, gtk.keysyms._6, gtk.keysyms.Right]:  # Right arrow
                command = 'RIGHT'

            elif event.keyval in [gtk.keysyms.KP_Down, gtk.keysyms.KP_2, gtk.keysyms._2, gtk.keysyms.Down]:  # Down arrow
                command = 'BOTTOM'

            elif event.keyval in [gtk.keysyms.KP_Begin, gtk.keysyms.KP_5, gtk.keysyms._5]:  # Centre
                command = 'ALL'

            elif event.keyval in [gtk.keysyms.KP_Insert, gtk.keysyms.KP_0, gtk.keysyms._0]:  # Delete the boxes
                command = 'DELETE'

            elif event.keyval in [gtk.keysyms.KP_End, gtk.keysyms.KP_1, gtk.keysyms._1]:  # Merge the boxes
                command = 'MERGE'

            elif event.keyval in [gtk.keysyms.KP_Page_Down, gtk.keysyms.KP_3, gtk.keysyms._3]:  # Split the boxes
                command = 'SPLIT'

        elif event.keyval in [gtk.keysyms.space, gtk.keysyms.Return, gtk.keysyms.KP_Enter]: # Move to next box
            command = 'NEXT'

        elif event.keyval in [gtk.keysyms.BackSpace]: # Move to previous box
            command = 'PREVIOUS'

        elif event.keyval <= 0xFD00: # Update box with character and move to next box
            command = 'CHANGECHAR'

        if command in ['LEFT', 'RIGHT', 'TOP', 'BOTTOM', 'ALL']:
            if control and not shift and not alt:
                self.stretch_boxes(command, False)
                return True
            elif control and shift and not alt:
                self.stretch_boxes(command, True)
                return True
            elif not control and not shift and alt:
                self.move_boxes(command)
                return True

        elif command in ['DELETE']:
            if control and not shift and not alt:
                self.delete_boxes()
                return True

        elif command in ['MERGE']:
            if control and not shift and not alt:
                self.merge_boxes()
                return True

        elif command in ['SPLIT']:
            if control and not shift and not alt:
                self.split_boxes()
                return True
        
        elif command in ['NEXT']:
            self.next_box()
            return True

        elif command in ['PREVIOUS']:
            self.previous_box()
            return True

        elif command in ['CHANGECHAR']:
            self.change_char_in_boxes(event.keyval)
            self.next_box()
            return True

        return False


    def stretch_boxes(self, direction, shrink):

        if shrink:
            step = -1
        else:
            step = 1

        for box in self.boxList:
            box.stretch(direction, step)

        self.newBoxList = self.boxList

        self.update_boxes()


    def move_boxes(self, direction):
        step = 1
        for box in self.boxList:
            box.move(direction, step)

        self.newBoxList = self.boxList
        self.update_boxes()

    def change_char_in_boxes(self, keyval):
        """Changes the character in the selected boxes"""
        pt = gtk.gdk.keyval_to_unicode(keyval) #Returns Unicode code point, or zero if none found

        if pt != 0: # No suitable unicode found, don't change
            char = unichr(pt)
            for box in self.boxList:
                box.set_text(char)

            self.newBoxList = self.boxList
            self.update_boxes()

    def get_current_box(self):
        """If there is a selection, updates the lines which are selected.
        Otherwise, updates the line which contains the cursor"""

        if self.blockUpdates:
            return

        bounds = self.textBuffer.get_selection_bounds()

        # get all selected lines
        if bounds:
            topLine = bounds[0].get_line()  # top line
            btmLine = bounds[1].get_line() # bottom line

        # just the line with the cursor
        else:
            cursor = self.textBuffer.get_mark('insert')
            iterAtCursor = self.textBuffer.get_iter_at_mark(cursor)

            topLine =  btmLine = iterAtCursor.get_line() # this is the line holding the box to draw

        #get the textIters wrapping the complete lines
        self.topIter = self.textBuffer.get_iter_at_line(topLine)   # start of the first selected line
        self.btmIter = self.textBuffer.get_iter_at_line(btmLine+1) # start of the line below the selection

        self.read_current_box()


    def read_current_box(self):
        """Reads the currently selected text into memory, ready for display"""

        strings = self.textBuffer.get_text(self.topIter, self.btmIter).split('\n')
        self.boxList = []

        for i in range(len(strings)):
            string = strings[i]

            if string == '': #skip blank lines
                continue

            box = TesseractBox(string)

            if box.valid:
                self.boxList.append(box)
            else:
                print 'Invalid line: %s' % string
                #TODO highlight line

        self.userScrolled = False # regain control of the image scrolling
        self.redraw_drawing_area()

    def next_box(self):
        """Moves to the next box in the boxfile (by moving the TextBuffer down one line).
           If multiple lines are selected, moves to the line after the last selected line."""

        bounds = self.textBuffer.get_selection_bounds()

        # jump to next line after selection
        if bounds:
            self.topIter = bounds[1]

        # jump to next line after cursor
        self.btmIter.forward_line() 
        # Haven't hit the end
        if self.topIter.forward_line():
            self.textBuffer.place_cursor(self.topIter)

        self.get_current_box() # Redraw

    def previous_box(self):
        """Moves to the previous box, or the one before the first selected line."""

        bounds = self.textBuffer.get_selection_bounds()

        # jump to line before selection
        if bounds:
            self.btmIter = bounds[0]

        # jump to line before cursor
        self.btmIter.backward_line()
        # Haven't hit the end
        if self.topIter.backward_line():
            self.textBuffer.place_cursor(self.topIter)

        self.get_current_box() # Redraw

    def set_checkbox_values(self, box):
        """Set the checkbox values based on a box"""

        self.userSetAttributes = False #prevent the toggle checkboxes callback firing

        self.italicButton.set_active(box.italic)
        self.boldButton.set_active(box.bold)
        self.ulineButton.set_active(box.uline)

        self.userSetAttributes = True


    def set_text_attributes(self, box):
        """Set the text attributes baed on box"""

        if box.italic:
            self.pangoAttrList.change(pango.AttrStyle(pango.STYLE_ITALIC, 0, -1))
        else:
            self.pangoAttrList.change(pango.AttrStyle(pango.STYLE_NORMAL, 0, -1))

        if box.bold:
            self.pangoAttrList.change(pango.AttrWeight(pango.WEIGHT_BOLD, 0, -1))
        else:
            self.pangoAttrList.change(pango.AttrWeight(pango.WEIGHT_NORMAL, 0, -1))

        if box.uline:
            self.pangoAttrList.change(pango.AttrUnderline(pango.UNDERLINE_SINGLE, 0, -1))
        else:
            self.pangoAttrList.change(pango.AttrUnderline(pango.UNDERLINE_NONE, 0, -1))


    def set_pen_colour(self, colour):
        """Set the drawing area pen colour"""

        parsedColour = gtk.gdk.color_parse(colour)
        self.drawingGC.set_rgb_fg_color(parsedColour)  # color of rectangle


    def redraw_drawing_area(self):
        '''redraw area of selected symbol + add rectangle'''

        if self.pixbuf and self.drawingArea.window:

            vertOffset = int( self.scrolledWindow.get_vadjustment().value )
            visibleHeight = int( self.scrolledWindow.get_vadjustment().page_size )

            horzOffset = int( self.scrolledWindow.get_hadjustment().value )
            visibleWidth = int( self.scrolledWindow.get_hadjustment().page_size )

            self.drawingArea.window.draw_pixbuf(self.drawingGC, self.pixbuf,
                            horzOffset, vertOffset,
                            horzOffset, vertOffset,
                            width=int(visibleWidth), height=int(visibleHeight))

            if self.boxList:

                if not self.userScrolled:
                    #centre on the first box
                    hAdj = self.scrolledWindow.get_hadjustment()
                    newHAdjValue = self.boxList[0].left - visibleWidth/2.0
                    newHAdjValue = max(0, newHAdjValue)
                    newHAdjValue = min(hAdj.upper - visibleWidth, newHAdjValue)

                    #only move the window if it is a "significant" move
                    if abs(hAdj.value - newHAdjValue) > 100:
                        hAdj.value = newHAdjValue

                    vAdj = self.scrolledWindow.get_vadjustment()
                    newVAdjValue = self.pixbuf.get_height() - self.boxList[0].top - visibleWidth/2.0
                    newVAdjValue = max(0, newVAdjValue)
                    newVAdjValue = min(vAdj.upper - visibleHeight, newVAdjValue)

                    if abs(vAdj.value - newVAdjValue) > 100:
                        vAdj.value = newVAdjValue

                #set checkboxes based on the first box
                self.set_checkbox_values(self.boxList[0])

                # draw all selected boxes
                for box in self.boxList:

                    if box.text.isupper():
                        self.set_pen_colour(self.uppercaseColour)
                    else:
                        self.set_pen_colour(self.lowercaseColour)

                    # draw the rectange described by self.box
                    segments = [(box.left, self.pixbuf.get_height() - box.top),
                                (box.right, self.pixbuf.get_height() - box.top),
                                (box.right, self.pixbuf.get_height() - box.bottom),
                                (box.left, self.pixbuf.get_height() - box.bottom),
                                (box.left, self.pixbuf.get_height() - box.top)]

                    self.drawingArea.window.draw_lines(self.drawingGC, segments)


                    #set the text attributes
                    self.set_text_attributes(box)

                    #set the text
                    self.pangoLayout.set_text(box.text)
                    (width, height) = self.pangoLayout.get_pixel_size()

                    textPosX = (box.left + box.right - width) /2.0
                    textPosY = self.pixbuf.get_height() - box.bottom + self.boxLabelOffset

                    #draw the text
                    self.drawingArea.window.draw_layout(self.drawingGC, int(textPosX), int(textPosY), self.pangoLayout)


    def check_files(self):
        '''
        Make sure that the image, box files exists
        '''
        try:
            fc = open(self.loadedImageFilename, 'r')
            fc.close()
        except IOError:
            self.error_dialog('Cannot find the %s file' % self.loadedImageFilename,
                             self.window)
            return False

        try:
            fb = open(self.loadedBoxFilename, 'r')
            fb.close()
        except IOError:
            self.error_dialog('Cannot find the %s file' % self.loadedBoxFilename,
                             self.window)
            return False
        return True


    def do_file_open(self, action):
        chooser = gtk.FileChooserDialog('Open Image', self.window,
                gtk.FILE_CHOOSER_ACTION_OPEN, (gtk.STOCK_CANCEL,
                gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))

        chooser.set_current_folder(self.currentPath)

        filter = gtk.FileFilter()
        filter.set_name('TIFF files')
        filter.add_pattern('*.tif')
        filter.add_pattern('*.tiff')
        chooser.add_filter(filter)

        filter = gtk.FileFilter()
        filter.set_name('Image files')
        filter.add_pattern('*.jpg')
        filter.add_pattern('*.jpeg')
        filter.add_pattern('*.png')
        filter.add_pattern('*.bmp')
        filter.add_pattern('*.tif')
        filter.add_pattern('*.tiff')
        chooser.add_filter(filter)

        filter = gtk.FileFilter()
        filter.set_name('All files')
        filter.add_pattern('*')
        chooser.add_filter(filter)

        response = chooser.run()
        if response == gtk.RESPONSE_OK:
            self.loadedImageFilename = chooser.get_filename()
            self.load_image_and_boxes()

        chooser.destroy()


    def do_file_save(self, action):
        self.save_boxfile()


    def do_file_save_as(self, action):

        chooser = gtk.FileChooserDialog('Save Boxfile and Image', self.window,
                gtk.FILE_CHOOSER_ACTION_SAVE, (gtk.STOCK_CANCEL,
                gtk.RESPONSE_CANCEL, gtk.STOCK_SAVE, gtk.RESPONSE_OK))

        chooser.set_current_folder(self.currentPath)

        filter = gtk.FileFilter()
        filter.set_name('Boxfiles')
        filter.add_pattern('*.box')
        chooser.add_filter(filter)

        response = chooser.run()
        if response == gtk.RESPONSE_OK:
            oldBoxFilename = self.loadedBoxFilename
            self.loadedBoxFilename = chooser.get_filename()

            # catch no extension
            try:
                (name, extension) = self.loadedBoxFilename.rsplit('.', 1)
            except ValueError: #no extension
                name = self.loadedBoxFilename
                extension = '.box'

            #update filenames
            oldImageFilename = self.loadedImageFilename

            self.loadedBoxFilename = name + extension
            self.loadedImageFilename = name + '.tif'

            self.save_boxfile(oldBoxFilename)


            #copy image to go with new boxfile
            if oldImageFilename != self.loadedImageFilename:
                shutil.copyfile(oldImageFilename, self.loadedImageFilename)

            self.update_filename()
        chooser.destroy()

    def autosave_boxfile(self):
        """Save an autosave file"""

        string = self.get_all_text()

        saveFile = open(self.loadedBoxFilename+'.autosave', 'w')
        saveFile.write(string)
        saveFile.close()

    def remove_autosave_file(self, filename=None):
        """Remove the autosave file, if it exists"""

        if filename:
            autosaveFilename = filename
        else:
            autosaveFilename = self.loadedBoxFilename

        autosaveFilename += '.autosave'

        if os.path.exists(autosaveFilename):
            if self.DEBUG:
                print 'Removing autosave file: %s' % autosaveFilename
            os.remove(autosaveFilename)

    def save_boxfile(self, oldFilename=None):
        """Saves the current boxfile to the current filename
        The autosave file corresponding to oldfilename, if it exists,
        otherwise self.loadedBoxFilename, will be removed
        """

        string = self.get_all_text()

        saveFile = open(self.loadedBoxFilename, 'w')
        saveFile.write(string)
        saveFile.close()

        if self.DEBUG:
            print 'Saved file: %s' % self.loadedBoxFilename

        self.remove_autosave_file(oldFilename)

        self.boxfileChangedSinceSave = False


    def do_undo(self, action):
        self.undo_change()


    def do_redo(self, action):
        self.redo_change()

    # HELP ACTIONS ###########
    def do_help_about(self, action):
        """Show the About dialog"""
        dialog = gtk.Dialog('About %s'%NAME, self.window,
                            gtk.DIALOG_NO_SEPARATOR | gtk.DIALOG_MODAL,
                            (gtk.STOCK_OK, gtk.RESPONSE_OK))
        dialog.set_size_request(450, 250)
        label = gtk.Label('''
%s version %s
Website: moshpytt.googlecode.com

Copyright 2011 John Beard <john.j.beard at gmail.com>
Copyright 2010 Zdenko Podobný <zdenop at gmail.com>
Copyright 2008 Mihail Radu Solcan (djvused and image maps)
Copyright 2007 Cătălin Frâncu <cata at francu.com>

This program is free software: you can redistribute it and/or
modify it under the terms of the GNU General Public License v3
''' % (NAME, VERSION))
        label.set_line_wrap(True)
        dialog.vbox.pack_start(label, True, True, 0)
        label.show()
        dialog.run()
        dialog.destroy()


    def do_help_shortcuts(self, action):
        """Display a dialog showing the keyboard shortcuts"""
        dialog = gtk.Dialog('Keyboard shortcuts', self.window,
                            gtk.DIALOG_NO_SEPARATOR | gtk.DIALOG_MODAL,
                            (gtk.STOCK_OK, gtk.RESPONSE_OK))

       #dialog.set_size_request(450, 250)
        label = gtk.Label(
'''Keyboard shortcuts

Directions: 8 - Up, 4 - Left, 6 - Right, 2 - Down, 5 - All
Ctrl-direction: Stretch box in direction
Ctrl-shift-direction: Shrink box in direction
Alt-direction: Move box in direction

Ctrl-0: Delete selected boxes
Ctrl-1: Merge selected boxes
Ctrl-2: Split selected boxes

Ctrl-Z: Undo change
Ctrl-Y: Redo change

''')
        label.set_line_wrap(True)
        dialog.vbox.pack_start(label, True, True, 0)
        label.show()
        dialog.run()
        dialog.destroy()


    def do_merge_boxes(self, action):
        self.merge_boxes()

    # BOX EDITING ACTIONS #########
    def do_delete_boxes(self, action):
        self.delete_boxes()


    def do_split_boxes(self, action):
        self.split_boxes()


    def do_quit(self, mi=None, action=None):

        if not self.confirm_close():
            return True

        gtk.main_quit()


    def get_all_text(self):
        bounds = self.textBuffer.get_bounds()
        return self.textBuffer.get_text(bounds[0], bounds[1])


    ### UNDO/REDO HANDLING ###

    def apply_change(self, change):

        if not change:
            return

        # invert the action
        if change['action'] == 'INS':
            change['action'] = 'DEL'
        elif change['action'] == 'DEL':
            change['action'] = 'INS'

        if change['action'] == 'DEL':
            self.blockUndoRedo = True

            offset = change['offset']
            startIter = self.textBuffer.get_iter_at_offset(offset)
            endIter = self.textBuffer.get_iter_at_offset(offset + len(change['text']) )
            self.textBuffer.delete(startIter, endIter)
        elif change['action'] == 'INS':
            self.blockUndoRedo = True

            startIter = self.textBuffer.get_iter_at_offset(change['offset'])
            self.textBuffer.insert(startIter, change['text'])


    def undo_change(self):
        change = self.undoRedoStack.undo()
        self.apply_change(change)


    def redo_change(self):
        change = self.undoRedoStack.redo()
        self.apply_change(change)


    ### BOX ACTIONS ###
    def delete_boxes(self):
        self.deleteBoxes = True
        self.update_boxes()


    def split_boxes(self):

        self.newBoxList = []

        for box in self.boxList:

            leftBox = box
            rightBox = copy.deepcopy(box)

            center = int((box.right + box.left) / 2)

            print center

            leftBox.right = center
            rightBox.left = center

            self.newBoxList.append(leftBox)
            self.newBoxList.append(rightBox)

        self.update_boxes()


    def merge_boxes(self):
        """Merge two or more boxes into a larger box. The resultant box will be
        the minimum box enclosing all selected boxes."""

        newBox = TesseractBox()

        newBox.page = self.boxList[0].page

        for box in self.boxList:

            if newBox.left != None:
                newBox.left = min (newBox.left, box.left)
            else:
                newBox.left = box.left

            if newBox.right != None:
                newBox.right = max (newBox.right, box.right)
            else:
                newBox.right = box.right

            if newBox.top != None:
                newBox.top = max (newBox.top, box.top)
            else:
                newBox.top = box.top

            if newBox.bottom != None:
                newBox.bottom = min (newBox.bottom, box.bottom)
            else:
                newBox.bottom = box.bottom

            if newBox.page != None:
                newBox.page = min (newBox.page, box.page)
            else:
                newBox.page = box.page

            newBox.text = newBox.text + box.text #concentenate the strings into the new box

            newBox.check_numbers() #check for flipped l/r, t/b

        self.newBoxList = [ newBox ] #replace the boxlist
        self.update_boxes()


    def update_boxes(self):
        """Updates the text buffer with the boxes in newBoxList, done after
        operations like merging, deleting and splitting."""

        self.blockUpdates = True

        self.textBuffer.delete(self.topIter, self.btmIter)

        topLine = self.topIter.get_line()

        if not self.deleteBoxes: # we want to insert new ones after deleting old ones

            if self.newBoxList:
                self.boxList = self.newBoxList

            boxString = ''
            for box in self.boxList:
                boxString += box.make_string()+'\n'

            self.textBuffer.insert(self.topIter, boxString)

            self.newBoxList = None #clear this variable

        if self.deleteBoxes: #reset this flag
            self.deleteBoxes = False
        else:#place cursor on the top line

            self.topIter = self.textBuffer.get_iter_at_line(topLine)

            self.btmIter = self.textBuffer.get_iter_at_line(topLine+len(self.boxList))
            self.btmIter.backward_char()

            if len(self.boxList) < 2:
                self.textBuffer.place_cursor(self.topIter)
            else:

                self.textBuffer.select_range(self.topIter, self.btmIter)

        self.blockUpdates = False

        self.get_current_box()
        self.redraw_drawing_area()


    def confirm_close(self):

        if not self.boxfileChangedSinceSave: #close straight away if no changes to boxfile
            return True

        dir, filename = os.path.split(self.loadedBoxFilename)

        dialog = gtk.MessageDialog(self.window, gtk.DIALOG_DESTROY_WITH_PARENT,
                                type=gtk.MESSAGE_QUESTION,
                                buttons=gtk.BUTTONS_NONE,
                                message_format="The file %s is not saved."%filename)

        dialog.format_secondary_text("Do you want to save it before closing?")

        dialog.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        dialog.add_button(gtk.STOCK_CLEAR, gtk.RESPONSE_NO)
        dialog.add_button(gtk.STOCK_SAVE, gtk.RESPONSE_YES);

        dialog.set_default_response(gtk.RESPONSE_NO);

        response = dialog.run()
        dialog.hide()

        if response == gtk.RESPONSE_NO:
            self.remove_autosave_file() #junk the autosave file
            return True
        if response == gtk.RESPONSE_YES:
            self.save_boxfile()
            return True

        return False # don't close


    def make_menu(self):
        uiManager = gtk.UIManager()
        self.accelGroup = uiManager.get_accel_group()
        self.window.add_accel_group(self.accelGroup)
        self.actionGroup = gtk.ActionGroup('UIManagerExample')
        self.actionGroup.add_actions(
            [('Open', gtk.STOCK_OPEN, '_Open Image/Boxfile...', '<Control>O', None,
              self.do_file_open),
             ('Save', gtk.STOCK_SAVE, '_Save Boxfile', '<Control>S', None,
              self.do_file_save),
             ('SaveAs', gtk.STOCK_SAVE_AS, 'Save Boxfile/Image _As...', '<Shift><Control>S', None,
              self.do_file_save_as),
             ('Quit', gtk.STOCK_QUIT, '_Quit', '<Control>Q', None, self.do_quit),
             ('File', None, '_File'),
             ('Edit', None, '_Edit'),
             ('Undo', gtk.STOCK_UNDO, '_Undo', '<Control>Z', None, self.do_undo),
             ('Redo', gtk.STOCK_REDO, '_Redo', '<Control>Y', None, self.do_redo),
             ('MergeBoxes', None, '_Merge Selected Boxes', '<Control>1', None, self.do_merge_boxes),
             ('SplitBoxes', None, '_Split Selected Boxes', '<Control>3', None, self.do_split_boxes),
             ('DeleteBoxes', gtk.STOCK_DELETE, '_Delete Selected Boxes', '<Control>0', None, self.do_delete_boxes),
             ('Help', None, '_Help'),
             ('About', gtk.STOCK_ABOUT, '_About', None, None, self.do_help_about),
             ('Shortcuts', None, '_Keyboard Shortcuts', None, None,
              self.do_help_shortcuts),
             ])
        uiManager.insert_action_group(self.actionGroup, 0)
        uiManager.add_ui_from_string(MENU)
        self.menuBar = uiManager.get_widget('/MenuBar')


    def update_filename(self):

        self.window.set_title('%s - v%s: %s' % \
                (NAME, VERSION, self.loadedBoxFilename))

        self.currentPath = os.path.dirname(self.loadedBoxFilename)


    def load_image(self):

        self.pixbuf = gtk.gdk.pixbuf_new_from_file(self.loadedImageFilename)

        if self.DEBUG:
            print datetime.now(), 'File %s is opened.' % self.loadedImageFilename

        if self.DEBUG:
            print datetime.now(), 'Displaying image...'
        self.drawingArea.set_size_request(self.pixbuf.get_width(),
                self.pixbuf.get_height())


    def load_image_and_boxes(self):

        (name, extension) = self.loadedImageFilename.rsplit('.', 1)
        self.loadedBoxFilename = name + '.box'

        filesOK = self.check_files()
        if not filesOK:
            return False

        self.load_image()
        self.load_boxfile()
        self.update_filename()

        if self.DEBUG:
            print datetime.now(), \
                'Function load_image_and_boxes is finished.'

        return True


    def load_boxfile(self):

        boxFile = codecs.open(self.loadedBoxFilename, 'r', 'utf-8')

        if self.DEBUG:
            print datetime.now(), 'Boxfile %s is opened.' % self.loadedBoxFilename

        self.blockUndoRedo = True #we don't want to allow the user to undo the boxfile load


        self.textBuffer.set_text(boxFile.read()) #read in the file
        self.textBuffer.place_cursor(self.textBuffer.get_iter_at_offset(0)) #place cursor at the start

        self.boxfileChangedSinceSave = False # nothing has been changed yet


    def setup_icons(self):
        """Set the application icons at different sizes"""

        iconDirectory = os.path.join(sys.path[0], 'icons')

        #FIXME probably there is a better way to do this
        iconFilename = os.path.join(iconDirectory, 'moshpytt-logo-16.svg')
        iconPixBuf16 = gtk.gdk.pixbuf_new_from_file(iconFilename)

        iconFilename = os.path.join(iconDirectory, 'moshpytt-logo-22.svg')
        iconPixBuf22 = gtk.gdk.pixbuf_new_from_file(iconFilename)

        iconFilename = os.path.join(iconDirectory, 'moshpytt-logo-32.svg')
        iconPixBuf32 = gtk.gdk.pixbuf_new_from_file(iconFilename)

        iconFilename = os.path.join(iconDirectory, 'moshpytt-logo-48.svg')
        iconPixBuf48 = gtk.gdk.pixbuf_new_from_file(iconFilename)

        gtk.window_set_default_icon_list( iconPixBuf16, iconPixBuf22, iconPixBuf32, iconPixBuf48)


    def setup_widgets(self):

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.connect('delete-event', self.do_quit)

        self.window.set_title('pyTesseractTrainer - Tesseract Boxfile '
                              + 'Editor version %s'
                              % (VERSION))

        self.setup_icons()
        self.window.set_size_request(900, 600)
        self.window.connect('key-press-event', self.on_entry_key_press)

        # the two pane layout for menu and main window
        vbox = gtk.VBox(False, 2)
        self.window.add(vbox)
        vbox.show()

        self.make_menu()
        vbox.pack_start(self.menuBar, False)

        # two pane layout for image and text
        hpaned = gtk.HPaned()
        hpaned.set_position(self.panePosition)
        vbox.pack_start(hpaned)
        hpaned.show()

        # set up the top pane - scrolled window
        self.scrolledWindow = gtk.ScrolledWindow()
        self.scrolledWindow.set_policy(gtk.POLICY_AUTOMATIC,
                gtk.POLICY_AUTOMATIC)
        hpaned.pack1(self.scrolledWindow, True, True)
        self.scrolledWindow.show()

        # set up the drawing area for the image
        self.drawingArea = gtk.DrawingArea()



        #set the pango context for the box labels

        pangoContext = self.drawingArea.create_pango_context()
        self.pangoLayout = pango.Layout(pangoContext)

        self.pangoAttrList = pango.AttrList()
        self.pangoLayout.set_attributes(self.pangoAttrList)

        boxLabelFontDesc = pango.FontDescription("monospace")
        boxLabelFontDesc.set_size(pango.SCALE * self.boxLabelFontSize)
        self.pangoLayout.set_font_description(boxLabelFontDesc)

        self.redrawHandlerID = self.drawingArea.connect('expose-event', self.on_redraw)
        self.scrolledWindow.add_with_viewport(self.drawingArea)

        #connect the scrollbar widgets
        self.scrolledWindow.get_hscrollbar().connect('change-value', self.on_scroll_image)
        self.scrolledWindow.get_vscrollbar().connect('change-value', self.on_scroll_image)

        self.drawingArea.show()

        # set up the right pane - textview
        self.textBuffer = gtk.TextBuffer()

        # set up the text pane
        self.textBox = gtk.TextView()
        self.textBox.set_buffer(self.textBuffer)

        self.textBox.set_left_margin(self.textBufferMargin)

        textBoxFontDesc = pango.FontDescription("monospace")
        textBoxFontDesc.set_size(pango.SCALE * self.textBoxFontSize)
        self.textBox.modify_font( textBoxFontDesc)

        self.textScroll = gtk.ScrolledWindow()
        self.textScroll.add_with_viewport(self.textBox)
        self.textScroll.set_policy(gtk.POLICY_AUTOMATIC,
                                   gtk.POLICY_AUTOMATIC)
        hpaned.pack2(self.textScroll, False, True)
        self.textScroll.show()

        self.textBox.show()

        #connect the text signals
        self.textBuffer.connect('changed', self.on_buffer_changed)
        self.textBuffer.connect('mark-set', self.on_mark_set)
        self.textBuffer.connect('delete-range', self.on_delete_range)
        self.textBuffer.connect('insert-text', self.on_insert_text)

        # button box
        self.buttonBox = gtk.HBox(False, 0)
        vbox.pack_start(self.buttonBox, False, False, 2)
        self.buttonBox.show()

        b = gtk.CheckButton('_Bold', True)
        self.buttonBox.pack_start(b, False, False, 10)
        b.connect('toggled', self.on_checkbutton_toggled, 'BOLD')
        b.add_accelerator('activate', self.accelGroup, ord('B'),
                          gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
        b.show()
        self.boldButton = b

        b = gtk.CheckButton('_Italic', True)
        self.buttonBox.pack_start(b, False, False, 10)
        b.connect('toggled', self.on_checkbutton_toggled, 'ITALIC')
        b.add_accelerator('activate', self.accelGroup, ord('I'),
                          gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
        b.show()
        self.italicButton = b

        b = gtk.CheckButton('_Underline', True)
        self.buttonBox.pack_start(b, False, False, 10)
        b.connect('toggled', self.on_checkbutton_toggled, 'ULINE')
        b.add_accelerator('activate', self.accelGroup, ord('U'),
                          gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
        b.show()
        self.ulineButton = b


        self.findPrevButton = gtk.Button(label='Previous')
        self.buttonBox.pack_end(self.findPrevButton, False, False)
        self.findPrevButton.connect('clicked', self.on_find_clicked, False)
        self.findPrevButton.show()

        self.findNextButton = gtk.Button(label='Next')
        self.buttonBox.pack_end(self.findNextButton, False, False)
        self.findNextButton.connect('clicked', self.on_find_clicked, True)
        self.findNextButton.show()

        self.findEntry = gtk.Entry()
        self.findEntry.set_width_chars(8)
        self.buttonBox.pack_end(self.findEntry, False, False)
        self.findEntry.show()

        label = gtk.Label('Find:')
        self.buttonBox.pack_end(label, False, False)
        label.show()

        # and the window
        self.window.show()

        #our drawing GC
        self.drawingGC = self.drawingArea.window.new_gc()

    def set_options(self):
        """Set display parameters"""

        self.autosaveChangeLimit = 10 #number of changes to autosave after
        self.panePosition = 650 #position of divider between image and text
        self.boxLabelOffset = 2 # gap between the box and the label
        self.boxLabelFontSize = 20
        self.textBoxFontSize = 10
        self.textBufferMargin = 20
        self.lowercaseColour = 'red'
        self.uppercaseColour = 'blue'


    def set_options_from_arguments(self, opts):

        if opts.imageFile:
            self.loadedImageFilename = opts.imageFile
        else:
            self.loadedImageFilename = os.path.join(sys.path[0],
                                            'example-data', 'eng.arial.tif')
        self.DEBUG = opts.debug


    def __init__(self, opts):

        self.set_options_from_arguments(opts)

        # initialise the undo/redo stack
        self.undoRedoStack = UndoRedoStack()

        self.set_options()

        # set up the window
        self.setup_widgets()

        # load the image and boxfile
        self.load_image_and_boxes()

        self.main()


    def main(self):
        gtk.main()


# If the program is run directly or passed as an argument to the python
# interpreter then create a MoshPyTT instance and show it
if __name__ == "__main__":
    main()
