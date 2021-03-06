################################################################################
#
# Copyright (c) 2011-2012, Daniel Baeumges (dbaeumges@googlemail.com)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
################################################################################

from common import Logger, LogLevel, Utils
from optparse import OptionParser

import copy
import hashlib
import os
import random
import subprocess


# ================================================================================
# APK Wrapper Error
# ================================================================================
class APKWrapperError(Exception):   
    def __init__(self, theValue):        
        self.value = theValue

    def __str__(self):
        return repr(self.value)


# ================================================================================
# APK Wrapper
# ================================================================================
class APKWrapper:
    def __init__(self, theApkFile, theSdkPath='', theLogger=Logger()):
        self.apkFile = theApkFile
        self.sdkPath = Utils.addSlashToPath(theSdkPath)
        self.log = theLogger

        self.sampleId = random.randint(1, 1000000)
        self.apkFileName = Utils.splitFileIntoDirAndName(theApkFile)[1]
        self.apkPath = Utils.splitFileIntoDirAndName(theApkFile)[0]
        self.package = ''
        self.manifest = {'activityList':[],
                         'activityAliasList':[],
                         'serviceList':[],
                         'receiverList':[],
                         'providerList':[],
                         'uses-permission':[]}
        
        self.__extractFromPermissions()
        self.__extractApplication()

    def getId(self):
        """
        Return id
        """
        return self.sampleId

    def setId(self, theId):
        """
        Set id
        """
        self.sampleId = theId

    def getManifest(self):
        """
        Return manifest
        """
        return self.manifest

    def getApk(self):
        """
        Return APK.
        """
        return os.path.join(self.apkPath, self.apkFileName)        

    def getApkFileName(self):
        """
        Return APK file name.
        """
        return self.apkFileName

    def getApkName(self):
        """
        Return APK file name without extension
        """
        return self.apkFileName.rsplit('.', 1)[0]

    def getApkPath(self):
        """
        Return path to APK file.
        """
        return self.apkPath
        
    def getPackage(self):
        """
        Return package of app.
        """
        return self.package

    def getMd5Hash(self):
        """
        Return the MD5 Hash of the APK file.
        """
        md5 = hashlib.md5()
        return self.__getHash(md5)

    def getSha256Hash(self):
        """
        Return the SHA256 Hash of the APK file.
        """
        sha256 = hashlib.sha256()
        return self.__getHash(sha256)

    def __getHash(self, theAlg):
        blockSize = 2**16
        apkFile = open(self.getApk(), "r")
        while True:
            data = apkFile.read(blockSize)
            if not data:
                break
            theAlg.update(data)
        return theAlg.hexdigest()

    def getMainActivityName(self):
        """
        Returns the name of the main activity.
        If there is none, return None.
        """
        for activity in self.manifest['activityList']:
            if activity.has_key('intentFilterList'):
                for intentFilter in activity['intentFilterList']:
                    if intentFilter.has_key('action'):
                        if isinstance(intentFilter['action'], dict) and intentFilter['action'].has_key('android:name'):
                            if intentFilter['action']['android:name'] == 'android.intent.action.MAIN':
                                if activity.has_key('android:name'):
                                    return activity['android:name']
                                else:
                                    return None
                    if intentFilter.has_key('category'):
                        if isinstance(intentFilter['category'], dict) and intentFilter['category'].has_key('android:name'):
                            if intentFilter['category']['android:name'] == 'android.intent.category.LAUNCHER':
                                if activity.has_key('android:name'):
                                    return activity['android:name']
                                else:
                                    return None
        return None
    
    def getActivityNameList(self):
        """
        Return list of activity names.
        """
        activityList = []
        for activity in self.manifest['activityList']:
            if activity.has_key('android:name'):
                activityList.append(activity['android:name'])
        return activityList

    def getServiceNameList(self):
        """
        Return list of service names.
        """
        serviceList = []
        for service in self.manifest['serviceList']:
            if service.has_key('android:name'):
                serviceList.append(service['android:name'])
        return serviceList

    def __extractFromPermissions(self):
        """
        Extract package and permissions and store them in self.manifest
        """        
        try:
            args = ['%saapt' % Utils.getAaptPath(self.sdkPath),
                    'd', 'permissions',
                    self.apkFile]
            aapt = subprocess.Popen(args,
                                    stdout=subprocess.PIPE,
                                    stdin=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
        except OSError, osErr:
            raise APKWrapperError('Failed to start aapt \'%s\': %s' % (args, osErr.strerror))

        out = aapt.communicate()[0]
        outLines = out.split('\n')
        
        for line in outLines:
            if line.startswith('package: '):
                self.package = line[9:]
            elif line.startswith('uses-permission: '):
                self.manifest['uses-permission'].append(line[17:])
                

    class Level:
        START = 0
        APPL = 1
        APPL_ACTIVITY = 2
        APPL_SERVICE = 3
        APPL_RECEIVER = 4
        APPL_PROVIDER = 5
        APPL_ACTIVITY_ALIAS = 6
        USES_LIBRARY = 7
        INTENT_FILTER = 11
        INTENT_FILTER_ACTION = 12
        INTENT_FILTER_CATEGORY = 13
        INTENT_FILTER_DATA = 14
        META_DATA = 21
        GRANT_URI_PERMISSION = 31        
        
    def __extractApplication(self):
        """
        Extract application information and store them in self.manifest
        """
        # Modes
        level = self.Level.START
        mainLevel = self.Level.START
        subLevel = self.Level.START
        obj = {}
        mainObj = {}
        subObj = {}
        
        # Run aapt
        try:
            args = ['%saapt' % Utils.getAaptPath(self.sdkPath),
                    'd', 'xmltree',
                    self.apkFile,
                    'AndroidManifest.xml']
            aapt = subprocess.Popen(args,
                                    stdout=subprocess.PIPE,
                                    stdin=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
        except OSError, osErr:
            raise APKWrapperError('Failed to start aapt \'%s\': %s' % (args, osErr.strerror))
        out = aapt.communicate()[0]
        outLines = out.split('\n')

        for fullLine in outLines:
            line = fullLine.lstrip()
            self.log.dev(line)
            if mainLevel == self.Level.START:
                #
                # Main
                #
                if line.startswith('E: activity'): # Main
                    # Set level                    
                    mainLevel = self.Level.APPL_ACTIVITY
                    mainObj = self.__getInitialMainObj(mainLevel)
                    level = mainLevel
                    obj = self.__getInitialMainObj(mainLevel)                    

                elif line.startswith('E: service'): # Main
                    # Set level
                    mainLevel = self.Level.APPL_SERVICE
                    mainObj = self.__getInitialMainObj(mainLevel)
                    level = mainLevel
                    obj = self.__getInitialMainObj(mainLevel)

                elif line.startswith('E: provider'): # Main
                    # Set level
                    mainLevel = self.Level.APPL_PROVIDER
                    mainObj = self.__getInitialMainObj(mainLevel)
                    level = mainLevel
                    obj = self.__getInitialMainObj(mainLevel)

                elif line.startswith('E: receiver'): # Main
                    # Set level
                    mainLevel = self.Level.APPL_RECEIVER
                    mainObj = self.__getInitialMainObj(mainLevel)
                    level = mainLevel
                    obj = self.__getInitialMainObj(mainLevel)

                elif line.startswith('E: uses-library'): # Main
                    # Set level
                    mainLevel = self.Level.USES_LIBRARY
                    mainObj = self.__getInitialMainObj(mainLevel)
                    level = mainLevel
                    obj = self.__getInitialMainObj(mainLevel)
                    
            elif mainLevel > self.Level.START:
                #
                # Main
                #
                if line.startswith('E: activity'): # Main
                    # Finish
                    self.__finishLevel(level, obj, subObj)
                    self.__finishSubLevel(subLevel, subObj, mainObj)
                    self.__finishMainLevel(mainLevel, mainObj)

                    # Set level
                    mainLevel = self.Level.APPL_ACTIVITY
                    mainObj = self.__getInitialMainObj(mainLevel)
                    level = mainLevel
                    obj = self.__getInitialMainObj(mainLevel)

                elif line.startswith('E: service'): # Main
                    # Finish
                    self.__finishLevel(level, obj, subObj)
                    self.__finishSubLevel(subLevel, subObj, mainObj)
                    self.__finishMainLevel(mainLevel, mainObj)

                    # Set level
                    mainLevel = self.Level.APPL_SERVICE
                    mainObj = self.__getInitialMainObj(mainLevel)
                    level = mainLevel
                    obj = self.__getInitialMainObj(mainLevel)

                elif line.startswith('E: provider'): # Main
                    # Finish
                    self.__finishLevel(level, obj, subObj)
                    self.__finishSubLevel(subLevel, subObj, mainObj)
                    self.__finishMainLevel(mainLevel, mainObj)
                    
                    # Set level
                    mainLevel = self.Level.APPL_PROVIDER
                    mainObj = self.__getInitialMainObj(mainLevel)
                    level = mainLevel
                    obj = self.__getInitialMainObj(mainLevel)

                elif line.startswith('E: receiver'): # Main
                    # Finish
                    self.__finishLevel(level, obj, subObj)
                    self.__finishSubLevel(subLevel, subObj, mainObj)
                    self.__finishMainLevel(mainLevel, mainObj)
                    
                    # Set level
                    mainLevel = self.Level.APPL_RECEIVER
                    mainObj = self.__getInitialMainObj(mainLevel)
                    level = mainLevel
                    obj = self.__getInitialMainObj(mainLevel)

                elif line.startswith('E: uses-library'): # Main
                    # Finish
                    self.__finishLevel(level, obj, subObj)
                    self.__finishSubLevel(subLevel, subObj, mainObj)
                    self.__finishMainLevel(mainLevel, mainObj)
                    
                    # Set level
                    mainLevel = self.Level.USES_LIBRARY
                    mainObj = self.__getInitialMainObj(mainLevel)
                    level = mainLevel
                    obj = self.__getInitialMainObj(mainLevel)
                    

                #
                # Intent-Filter
                #
                elif line.startswith('E: intent-filter'): # Activity, Service, Receiver
                    # Finish
                    self.__finishLevel(level, obj, subObj)
                    self.__finishSubLevel(subLevel, subObj, mainObj)
                    
                    # Set level
                    subLevel = self.Level.INTENT_FILTER
                    subObj = self.__getInitialSubObj(subLevel)
                    level = subLevel
                    obj = self.__getInitialSubObj(subLevel)     
                
                elif line.startswith('E: action'): # Intent-Filter
                    # Finish
                    self.__finishLevel(level, obj, subObj)
                    
                    # Set level
                    level = self.Level.INTENT_FILTER_ACTION
                    obj = {}
                    
                elif line.startswith('E: category'): # Intent-Filter
                    # Finish
                    self.__finishLevel(level, obj, subObj)
                    
                    # Set level
                    level = self.Level.INTENT_FILTER_CATEGORY
                    obj = {}
                    
                elif line.startswith('E: data'): # Intent-Filter
                    # Finish
                    self.__finishLevel(level, obj, subObj)
                    
                    # Set level
                    level = self.Level.INTENT_FILTER_DATA
                    obj = {}


                #
                # Other
                #                    
                elif line.startswith('E: meta-data'): # Activity, Service, Receiver, Provider
                    # Finish
                    self.__finishLevel(level, obj, subObj)
                    self.__finishSubLevel(subLevel, subObj, mainObj)
                    
                    # Set level
                    subLevel = self.Level.META_DATA
                    level = subLevel
                    obj = self.__getInitialSubObj(subLevel)

                elif line.startswith('E: grant-uri-permission'): # Provider
                    # Finish
                    self.__finishLevel(level, obj, subObj)
                    self.__finishSubLevel(subLevel, subObj, mainObj)
                    
                    # Set level
                    subLevel = self.Level.META_DATA
                    level = subLevel
                    obj = self.__getInitialSubObj(subLevel)  
                    

                elif line.startswith('E: '):
                    self.log.debug('Unkown element found: %s' % line)
                    break
                

                #
                # Attributes
                #
                elif line.startswith('A: android'): # Attribute
                    # Extract attribute
                    exType = 0
                    attrName = ''
                    attrValue = ''
                    for char in line[3:]:
                        if exType == 0: # attribute name
                            if char == '(':
                                exType = 1
                            else:
                                attrName += char
                        elif exType == 1: # ignore (1)
                            if char == '=':
                                exType = 2
                        elif exType == 2: # ignore (2)
                            if char == '"':
                                exType = 3
                        elif exType == 3: # attribute value
                            if char == '"':
                                break
                            else:
                                attrValue += char
                    
                    if level >= self.Level.APPL and level <= self.Level.USES_LIBRARY:
                        mainObj[attrName] = attrValue
                    elif level == self.Level.INTENT_FILTER:
                        subObj[attrName] = attrValue
                    else:
                        obj[attrName] = attrValue
                        
            else: # level == Level.START
                if line.startswith('E: application'):
                    level = self.Level.APPL

        # Final Finish
        self.__finishLevel(level, obj, subObj)
        self.__finishSubLevel(subLevel, subObj, mainObj)
        self.__finishMainLevel(mainLevel, mainObj)

    def __getInitialMainObj(self, theMainLevel):
        if theMainLevel == self.Level.APPL_ACTIVITY or \
                theMainLevel == self.Level.APPL_SERVICE or \
                theMainLevel == self.Level.APPL_RECEIVER or \
                theMainLevel == self.Level.APPL_PROVIDER or \
                theMainLevel == self.Level.APPL_ACTIVITY_ALIAS:
            return {"intentFilterList":[]}
        else:
            return {}

    def __getInitialSubObj(self, theSubLevel):
        if theSubLevel == self.Level.INTENT_FILTER:
            return {'action':'',
                    'category':'',
                    'data':''}
        else:
            return {}
                    
    def __finishMainLevel(self, theMainLevel, theMainObj):
        if theMainLevel == self.Level.APPL_ACTIVITY:
            self.manifest['activityList'].append(copy.deepcopy(theMainObj))
        elif theMainLevel == self.Level.APPL_SERVICE:
            self.manifest['serviceList'].append(copy.deepcopy(theMainObj))
        elif theMainLevel == self.Level.APPL_RECEIVER:
            self.manifest['receiverList'].append(copy.deepcopy(theMainObj))
        elif theMainLevel == self.Level.APPL_PROVIDER:
            self.manifest['providerList'].append(copy.deepcopy(theMainObj))
        elif theMainLevel == self.Level.APPL_ACTIVITY_ALIAS:
            self.manifest['activityAliasList'].append(copy.deepcopy(theMainObj))
        theMainObj = {}

    def __finishSubLevel(self, theSubLevel, theSubObj, theMainObj):        
        if theSubLevel == self.Level.INTENT_FILTER and theMainObj.has_key('intentFilterList'):
            theMainObj['intentFilterList'].append(copy.deepcopy(theSubObj))
        theSubObj = {}

    def __finishLevel(self, theLevel, theObj, theSubObj):
        if theLevel == self.Level.INTENT_FILTER_ACTION:
            theSubObj['action'] = copy.deepcopy(theObj)
        elif theLevel == self.Level.INTENT_FILTER_CATEGORY:
            theSubObj['category'] = copy.deepcopy(theObj)
        elif theLevel == self.Level.INTENT_FILTER_DATA:
            theSubObj['data'] = copy.deepcopy(theObj)
        theObj = {}       


# ================================================================================
# Main method
# ================================================================================
def main():
    # Parse options
    parser = OptionParser(usage='usage: %prog [options] apk', version='%prog 0.1')    
    parser.add_option('', '--sdkPath', metavar='<path>', help='Set path to Android SDK')
    parser.add_option('-v', '--verbose', action='store_true', dest='verbose', default=True)
    parser.add_option('-q', '--quiet', action='store_false', dest='verbose')
    (options, args) = parser.parse_args()

    # Run   
    if options.verbose:
        logger = Logger(LogLevel.DEBUG)
    else:
        logger = Logger()
    apk = APKWrapper(args[0], theSdkPath=options.sdkPath, theLogger=logger)
    print apk.getManifest()
    print apk.getActivityNameList()
    print apk.getMainActivityName()
    print apk.getServiceNameList()
    print 'MD5 %s' % apk.getMd5Hash()
    print 'SHA256 %s' % apk.getSha256Hash()

    import codecs
    report = codecs.open('xxx', "w", "utf-8")
    report.write('md5: %s' % apk.getMd5Hash())

if __name__ == '__main__':
    main()
    
