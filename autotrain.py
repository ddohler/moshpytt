#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#       Autotrain is a script designed to help generate Tesseract training
#       data from image/boxfile pairs.
#
#       The order of execution is:
#           * Work out the language and a list of fonts present
#           * Generate .tr files from each boxfile
#           * Concatenate all .tr and .box files for each font into
#             single files
#           * Run unicharset_extractor on the boxfiles
#           * Run mftraining and cntraining
#           * Rename the output files to include the language prefix
#           * Run combine_tessdata on all the generated files
#           * Move the lang.traineddata file to the tesseract directory.
#             (you need to specify this directory in the script)
#
#       You must run this program only for one language at a time.
#
#       Because many Tesseract tools output files in the current working
#       directory, you must run this script from the directory holding your
#       images/boxfiles.
#
#       You must run the script with high enough permissions to allow the file
#       to be copied to the tesseract directory.
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

import subprocess
import os
import sys
import shutil
import codecs


class AutoTrainer:

    def __init__(self):
        self.tessdataDirectory = '/usr/local/share/tessdata'

    def generate_tr_files(self):

        for filename in self.baselist:  #for every file in the directory

            # generate the .tr files from the .tif/png + .box
            cmd = ['tesseract', '%s%s'%(filename, self.ext), filename, 'nobatch', 'box.train.stderr']
            subprocess.call(cmd)

    def generate_unicharset(self):

        print '\nGenerating unicharset'

        cmd = ['unicharset_extractor']
        cmd.extend(self.catBoxFileList)

        print 'Running command:', cmd
        subprocess.call(cmd)


    def do_mftraining(self):

        print '\nBeginning mftraining'

        cmd = ['mftraining', '-U', 'unicharset', '-O',  self.lang +'.unicharset']

        cmd.extend(self.catTrFileList)

        print 'Running command:', cmd
        subprocess.call(cmd)

    def do_cntraining(self):

        print '\nBeginning cntraining'
        cmd = ['cntraining']

        cmd.extend(self.catTrFileList)

        print 'Running command:', cmd
        subprocess.call(cmd)
        pass

    def rename_files(self):

        print '\nRenaming files'
        for filename in ['normproto', 'Microfeat', 'inttemp', 'pffmtable']:

            newFilename = '%s.%s' % (self.lang, filename)

            shutil.move(filename, newFilename)

    def combine_data(self):

        print '\nCombining data'
        cmd = ['combine_tessdata', self.lang + '.']
        print 'Running cmd:' , cmd
        subprocess.call(cmd)

    def get_language(self):

        self.lang = self.baselist[0].split('.')[0]

        print '\nFound language: %s' % self.lang

    def get_font_list(self):

        self.fontList = []
        for filename in self.baselist:

            font = filename.split('.')[1]

            if font not in self.fontList:
                self.fontList.append(font)

        print '\nFound fonts:', self.fontList

    def concatenate_files(self):

        print '\nConcatenating files'

        self.catBoxFileList = []
        self.catTrFileList = []

        for font in self.fontList:

            filesInFont = []
            for filename in self.baselist:

                fileFont = filename.split('.')[1]
                number = filename.split('.')[2]

                if font == fileFont:
                    filesInFont.append( filename )

            catBoxFilename = '%s.%s.box' % (self.lang, font)
            catTrFilename = '%s.%s.tr' % (self.lang, font)

            self.catBoxFileList.append(catBoxFilename)
            self.catTrFileList.append(catTrFilename)

            catBoxFile = codecs.open( catBoxFilename, 'w', 'utf-8')
            catTrFile = codecs.open( catTrFilename, 'w', 'utf-8')

            print '  Concat files:', catBoxFilename, catTrFilename

            for filename in filesInFont:
                boxFilename= filename+'.box'
                trFilename = filename+'.tr'

                boxFile = codecs.open(boxFilename, 'r', 'utf-8')
                trFile = codecs.open(trFilename, 'r', 'utf-8')

                for line in boxFile:
                    catBoxFile.write(line)

                for line in trFile:
                    catTrFile.write(line)

            print 'Concatenation complete for font: %s' % font

    def copy_traineddata(self):

        traineddata = self.lang+'.traineddata'

        print '\nMoving %s to tessdata directory: %s' % (traineddata, self.tessdataDirectory)

        try:
            shutil.copy( traineddata, self.tessdataDirectory )
        except IOError:
            print "Error: You don't have permisson to write to the tessdata directory."

    def generate_dawgs(self):

        print '\nGenerating DAWGs'

        listFilename = '%s.freq_list.txt' % self.lang
        if os.path.exists(listFilename):
            cmd = ['wordlist2dawg', listFilename, self.lang + '.freq-dawg', self.lang +'.unicharset' ]
            subprocess.call(cmd)

        listFilename = '%s.word_list.txt' % self.lang
        if os.path.exists(listFilename):
            cmd = ['wordlist2dawg', listFilename, self.lang + '.word-dawg', self.lang +'.unicharset' ]
            subprocess.call(cmd)

    def run(self):

        filelist = sorted(os.listdir(os.getcwd()))

        self.baselist = []
        for filename in filelist:
            (name, extension) = os.path.splitext(filename)
            if extension in ['.tif', '.png'] and name not in self.baselist:
                    self.ext = extension
                    self.baselist.append( name )
        print self.baselist

        self.get_language()
        self.get_font_list()

        self.generate_tr_files()
        self.concatenate_files()
        self.generate_unicharset()
        self.do_mftraining()
        self.do_cntraining()
        self.rename_files()
        self.generate_dawgs()
        self.combine_data()
        self.copy_traineddata()


if __name__ == "__main__":
    at = AutoTrainer()
    at.run()
