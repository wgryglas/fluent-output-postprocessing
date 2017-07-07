#! /usr/bin/python

import os
import re
import json
import numpy as np

"""
Program which converts the set of output Fluent files into single JSON data structure file. The JSON data file
can be easy read in Python or other programs therefore storing data in this structure is the most flexible approach.
Furthermore JSON file after loading into python object can allow to access variables and sub-data structures via
the dot member accessor - object.variableName or object.subStructureName.variableName. The data can be read into
other python script just by calling "read" function from this file.

========================================================================================================================
Reading data example:

from Parser import read
import os
import matplotlib.pyplot as plt

fileObject = Data("output.json")

print fileObject["FX"]["Forces (n)"]["Pressure"]["korpus"]
print fileObject.FX.Forces_n.Pressure.korpus


path_to_dirs="/dadsfsg/sdgf/"
listOfPressures = []
for dirname in os.listdir(path_to_dirs):
    fluentOut = read(path_to_dirs+os.sep+dirname)
    listOfPressures.append( fluentOut.FX.Forces_n.Pressure.korpus )

plt.plot(listOfPressure)
plt.show()


========================================================================================================================
Converting set of outputs



========================================================================================================================

JSON saving convention:
                            variable : value

where value can be one of: float, string, table([...]),  or collection of variables enclosed in { other_var:value, .... }.


Example output:
 "FX": {
        "Forces - Direction Vector (1 0 0)": {
            "Forces (n)": {
                "Pressure": {
                    "korpus": -10.571669,
                    "glowica": -21.163561,
                    "ster1": -7.6179511,
                    "ster3": -7.6231018,
                    "ster2": -7.6230002,
                    "zapalnik": -48.915993,
                    "ster4": -7.6217039,
                    "gardziel_dyszy": -12.613534,
                    "tail": -129.45906,
                    "Net": -253.20957
                }
            }
        }


The data is divided according to files:
{
    "Log" : {...}
    "Fx" : {...}
    "Fy" : {...}
    "Fz" : {...}
    "Mx" : {...}
    "My" : {...}
    "Mz" : {...}
    "CoPy" : {...}
    "CoPz" : {...}
}

Each file consist of own data members. It is possible to distinguish 2 type of files:
  * log file:
        "Log" :
        {
            "nIteration": <value>,
            "caseName": <value>,
            "residuals":
            {
                "continuity" : <value>,
                "z-velocity" : <value>,
                 .
                 .
                 .
            }
        }

    * force file:
        <ForceFileName> :          <-- e.g.: "FX"
        {
             <force name>:         <-- e.g.: "Forces - Direction Vector (1 0 0)"
             {
                <force group>:     <-- e.g.: "Forces (n)"
                {
                    <force type>:  <--  "Pressure", "Viscous", "Total"
                    {
                        <zone 1 name>: <value>
                        <zone 2 name>: <value>
                        <zone 3 name>: <value>
                        .
                        .
                        .
                    }
                }
             }
        }

    Note, for the CoP files <force name> section is not present because those files poses only one force calculator

========================================================================================================================
"""


def ropen(filename, buf_size=8192):
    """a generator that returns the lines of a file in reverse order"""
    with open(filename) as fh:
        segment = None
        offset = 0
        file_size = fh.seek(0, os.SEEK_END)
        total_size = remaining_size = fh.tell()
        while remaining_size > 0:
            offset = min(total_size, offset + buf_size)
            # fh.seek(file_size - offset)
            fh.seek(-offset, os.SEEK_END)
            buffer = fh.read(min(remaining_size, buf_size))
            remaining_size -= buf_size
            lines = buffer.split('\n')
            # the first line of the buffer is probably not a complete line so
            # we'll save it and append it to the last line of the next buffer
            # we read
            if segment is not None:
                # if the previous chunk starts right from the beginning of line
                # do not concact the segment to the last line of new chunk
                # instead, yield the segment first
                if buffer[-1] is not '\n':
                    lines[-1] += segment
                else:
                    yield segment
            segment = lines[0]
            for index in range(len(lines) - 1, 0, -1):
                if len(lines[index]):
                    yield lines[index]
        # Don't yield None if the file was empty
        if segment is not None:
            yield segment


class LogParser:
    def __init__(self, path):
        self.path = path
        self.output = dict()

    def parseCaseName(self):
        line = ""
        with open(self.path, "r") as f:
            while line.isspace() or 0 == len(line):
                line = f.readline()

        result = re.search(r'-i\s*([\w\s*]+)\.jou', line)
        if not result:
            raise Exception(
                "The line: " + line[:-1] + "\ndoes not contain -i ....jou sentence required to obtain case name")

        caseName = result.groups(0)[0]

        self.output["caseName"] = caseName

    def parseMachAlphaBoundaryCondition(self):
        # pressurefarfield no 89875. no 1.10 no 281.65 yes no -1. no 5e-5 no 0. no no yes 0.1 50.

        prevLine = re.compile(r'\(pressurefarfield\)')

        found = False
        with open(self.path, "r") as f:
            for line in f.readlines():
                if found:
                    res = re.split(r'\s+', line.strip().replace("no", "").replace("yes", ""))
                    res = map(float, res[1:])
                    farField = dict()
                    farField["static_pressure"] = res[0]
                    farField["mach"] = res[1]
                    farField["temperature"] = res[2]
                    farField["alpha"] = np.arctan(res[5] / res[3]) / np.pi * 180
                    self.output["farFieldConditions"] = farField
                    break

                if prevLine.search(line):
                    found = True

        if not found:
            print "The boundary conditions setup not found"

    def parseIterNumberAndResiduals(self):
        lineBuffer = []
        residualsMatcher = re.compile(r'\s*iter\s*')

        residualLine = ""

        for line in ropen(self.path):
            if residualsMatcher.match(line):
                residualLine = line
                break
            else:
                lineBuffer.append(line)

        residualNames = re.split(r'\s+', residualLine.strip())

        residualValues = []
        for line in lineBuffer[-1::-1]:
            tmp = re.split(r'\s+', line.strip())

            if len(tmp) != len(residualNames) + 1:
                break

            residualValues = tmp

        nIter = int(residualValues[0])
        self.output["nIteration"] = nIter

        residualNames = residualNames[1:-1]
        residualValues = map(float, residualValues[1:-2])
        self.output["residuals"] = dict(zip(residualNames, residualValues))

    def parse(self):
        self.parseCaseName()
        self.parseIterNumberAndResiduals()
        self.parseMachAlphaBoundaryCondition()


class ForceParser:
    def __init__(self, path, singleForce=False):
        self.path = path

        self.lineProcessor = self.parseForceTitle

        self.forceDict = dict()

        self.output = dict()

        self.zones = []

        self.lastForce = False

        self.singleForce = singleForce

        self.additionalForceDefinition = []


    def parseDocumentTitle(self, line):
        title = re.search(r'"Force Report"', line)
        if not title:
            raise "The file " + self.path + " does not seems to be Force Rreport. Can't parse it"

        self.lineProcessor = self.parseForceTitle

    def parseForceTitle(self, line):
        # For more than one force calculation
        if not self.singleForce:

            line = line.strip()

            if len(line) == 0 or line[0] == "\"":
                return

            names = re.findall(r'(([^\s][^\(]*)\s(\([^\)]+\)))', line)

            self.forceDict = dict()

            fullname = ""
            if len(names) > 0:
                for i, name in enumerate(names):
                    fullname += name[1]
                    if i < len(names) - 1:
                        fullname += " "

                    additional = name[1]
                    if re.search(r'-', additional):
                        additional = additional.split("-")[1].strip()

                    self.forceDict[additional] = map(float, re.split(r'\s+', name[2][1:-1]))
                    self.additionalForceDefinition.append(additional)
            else:
                name = re.search(r'\s*([^\s]+(\s{1,3}?[^\s]+)*)\s*', line)
                if not name:
                    self.lineProcessor = None
                    return
                else:
                    fullname = name.group(0)

            # Append empty force
            self.output[fullname] = self.forceDict

        else:  # When only single output is present, e. g. the CoPy file
            self.output = self.forceDict

        self.lineProcessor = self.parseForceGroups

    def parseForceGroups(self, line):

        res = re.findall(r'\s*([^\s]+(\s{1,3}?[^\s]+)*)\s*', line)
        if not res:
            raise Exception("The line: " + line.strip() +
                            "\ncould not be parsed to find force group names like Force (n), Coefficients")

        # Append empty gorups
        for groupName in res:
            self.forceDict[groupName[0]] = dict()

        self.lineProcessor = self.parseForceNames

    def parseForceNames(self, line):
        res = re.findall(r'\s*([^\s]+)\s+', line)

        if not res:
            raise Exception("The line " + line.strip() + "could not be parsed to obtain force names")

        forceNames = res[1:]

        nGroups = len(self.forceDict) - len(self.additionalForceDefinition)
        nForceTypes = int(len(forceNames) / nGroups)

        # Append force names to dictionary
        grId = 0
        for groupName in self.forceDict:
            if groupName in self.additionalForceDefinition:
                continue

            forceGroupDic = self.forceDict[groupName]
            for fid in range(nForceTypes):
                forceGroupDic[forceNames[grId * nForceTypes + fid]] = dict()

            grId += 1

        self.lineProcessor = self.parseForceValuesAndAssignToZone

    def parseForceValuesAndAssignToZone(self, line):

        if line[0] == "-":
            self.lastForce = True
            return

        res = re.search(r'([^\s]+)', line)
        zoneName = res.group(0)

        vectorRegex = re.compile(r'\(([^\)]+)')
        scalarRegex = re.compile(r'\s*([^\s]+)\s*')

        # Parse appropriate type
        if vectorRegex.search(line):
            res = vectorRegex.findall(line)
            values = map(lambda s: map(float, re.split("\s", s)), res)

        elif scalarRegex.search(line):
            res = scalarRegex.findall(line)
            values = map(float, res[1:])
        else:
            self.lineProcessor = None
            return

        nGroups = len(self.forceDict) - len(self.additionalForceDefinition)
        nForceTypes = len(values) / nGroups

        grId = 0
        for groupName in self.forceDict:
            if groupName in self.additionalForceDefinition:
                continue

            forceGroupDic = self.forceDict[groupName]
            for fid, forceName in enumerate(forceGroupDic):
                forceGroupDic[forceName][zoneName] = values[grId * nForceTypes + fid]
            grId += 1

        if self.lastForce:
            self.lastForce = False
            self.lineProcessor = self.parseForceTitle
            self.additionalForceDefinition = []

    def parse(self):
        with open(self.path, "r") as fptr:
            for line in fptr.readlines():

                # Skip empty line
                if len(line.strip()) == 0:
                    continue

                # Check if any processor left for predefined work
                if self.lineProcessor is None:
                    break

                # Process line
                self.lineProcessor(line)


FILES = {"Log" : "fluent_log.log",
         "FX"  : "FX",
         "FY"  : "FY",
         "FZ"  : "FZ",
         "MX"  : "MX",
         "MY"  : "MY",
         "MZ"  : "MZ",
         "CoPy": "CoPy",
         "CoPz": "CoPz"}

class DirectoryParser:
    def __init__(self, directoryPath):
        self.directory = directoryPath

        self.data = dict()

    def load(self):
        parsers = {"Log": LogParser(self.directory + os.sep + FILES["Log"]),
                   "FX": ForceParser(self.directory + os.sep + FILES["FX"]),
                   "FY": ForceParser(self.directory + os.sep + FILES["FY"]),
                   "FZ": ForceParser(self.directory + os.sep + FILES["FZ"]),
                   "MX": ForceParser(self.directory + os.sep + FILES["MX"]),
                   "MY": ForceParser(self.directory + os.sep + FILES["MY"]),
                   "MZ": ForceParser(self.directory + os.sep + FILES["MZ"]),
                   "CoPy": ForceParser(self.directory + os.sep + FILES["CoPy"], singleForce=True),
                   "CoPz": ForceParser(self.directory + os.sep + FILES["CoPz"], singleForce=True)}

        for name in parsers:
            parser = parsers[name]
            try:
                parser.parse()
            except IOError:
                print "Parser " + name + " error.\nCouldn't open file " + os.path.basename(parser.path)
            except Exception as e:
                print "Parser " + name + " error.\nCouldn't parse the " + os.path.basename(
                    parser.path) + " file\n" + e.message + "\n"

            if len(parser.output) != 0:
                self.data[name] = parser.output

    def dump(self, outputFile=None):
        if not outputFile:
            outputFile = "output.json"

        with open(outputFile, 'w') as fptr:
            json.dump(self.data, fptr, indent=4)


def writeCSV(fptr, titles, array2D):
    for name in titles[:-1]:
        fptr.write(name + ",")
    fptr.write(titles[-1] + "\n")

    for rowId, row in enumerate(array2D):
        for element in row[:-1]:
            fptr.write(str(element) + ",")
        newline = '\n'
        if rowId > len(array2D) - 1:
            newline = ''
        fptr.write(str(row[-1]) + newline)

class Data:
    def __init__(self, jsonPathOrDataDict):

        self.data = dict()

        if type(jsonPathOrDataDict) is str:
            with open(jsonPathOrDataDict, 'r') as fptr:
                self.data = json.load(fptr)
        elif type(jsonPathOrDataDict) is dict:
            self.data = jsonPathOrDataDict
        else:
            raise Exception("Data class constructor accepts only data dictionary or a path to a json dumped dictionary")

        self.simpleKeys = []

        self.__construct__accssors()

    def __construct__accssors(self):
        sources = [self.data]
        targets = [self.__dict__]

        for key in self.data:
            newKey = re.sub('\(|\)|\-|=', ' ', key).strip()
            newKey = re.sub('\s+', '_', newKey)

            self.simpleKeys.append(newKey)

            if type(self.data[key]) is dict:
                self.__dict__[newKey] = Data(self.data[key])
            else:
                self.__dict__[newKey] = self.data[key]

        # while len(sources) > 0:
        #     newSources = []
        #     newTargets = []
        #
        #     for i, source in enumerate(sources):
        #         target = targets[i]
        #
        #         for key in source:
        #             newKey = re.sub('\(|\)|\-', ' ', key).strip()
        #             newKey = re.sub('\s+', '_', newKey)
        #
        #             if type(source[key]) is dict:
        #                 target[newKey] = dict()
        #                 newTargets.append(target[newKey])
        #                 newSources.append(source[key])
        #             else:
        #                 target[newKey] = source[key]
        #
        #     sources = newSources
        #     targets = newTargets

    def __iter__(self):
        return self.__dict__

    def __getitem__(self, item):
        return self.data[item]

    @property
    def show(self):
        print self.simpleKeys

    def dumpJSON(self, outputFile=None):
        if not outputFile:
            outputFile = "output.json"

        with open(outputFile, 'w') as fptr:
            json.dump(self.data, fptr, indent=4)

    def table(self, componentName="Net"):
        mach = self.data["Log"]["farFieldConditions"]["mach"]
        alpha = self.data["Log"]["farFieldConditions"]["alpha"]

        cxGlobal, cyGlobal, czGlobal = self.data["FX"]["Forces"]["Coefficients"]["Total"][componentName]
        cmxGlobal, cmyGlobal, cmzGlobal = \
        self.data["MX"]["Moments - Moment Center"]["Coefficients"]["Total"][componentName]

        cxDV = self.data["FX"]["Forces - Direction Vector"]["Coefficients"]["Total"][componentName]
        cyDV = self.data["FY"]["Forces - Direction Vector"]["Coefficients"]["Total"][componentName]
        czDV = self.data["FZ"]["Forces - Direction Vector"]["Coefficients"]["Total"][componentName]

        cmxDV = self.data["MX"]["Moments - Moment Center Moment Axis"]["Coefficients"]["Total"][
            componentName]
        cmyDV = self.data["MY"]["Moments - Moment Center Moment Axis"]["Coefficients"]["Total"][
            componentName]
        cmzDV = self.data["MZ"]["Moments - Moment Center Moment Axis"]["Coefficients"]["Total"][
            componentName]

        titles = ['mach', 'alpha',
                  'CX-global', 'CY-global', 'CZ-global', 'CMX-global', 'CMY-global', 'CMZ-global',
                  'CX-dir', 'CY-dir', 'CZ-dir', 'CMX-dir', 'CMY-dir', 'CMZ-dir']

        values = [mach, alpha,
                  cxGlobal, cyGlobal, czGlobal, cmxGlobal, cmyGlobal, cmzGlobal,
                  cxDV, cyDV, czDV, cmxDV, cmyDV, cmzDV]

        return titles, values


if __name__ == "__main__":
    baseDir = "specification/VISCID BLOCK - surowe"
    outFile = "output.csv"

    parser = DirectoryParser(baseDir)
    parser.load()
    parser.dump()

    data = Data(parser.data)

    titles, values = data.table("Net")
    listOfData = [data, data, data]

    listOfValues = []
    for d in listOfData:
        titles, values = d.table("Net")
        listOfValues.append(values)


    with open("output.csv", "w") as fptr:
        writeCSV(fptr, titles, listOfValues)


    # print data.FX.Forces.Coefficients.Total.simpleKeys
    # print data["FX"]["Forces - Direction Vector"]["Coefficients"]["Total"]["glowica"]
    # print data.FX.Forces_Direction_Vector

