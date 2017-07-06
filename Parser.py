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

fileObject = read("output.json")

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
        #pressurefarfield no 89875. no 1.10 no 281.65 yes no -1. no 5e-5 no 0. no no yes 0.1 50.

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
                    farField["alpha"] = np.arctan(res[4]/res[3])/np.pi*180
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

            name = re.search(r'\s*([^\s]+(\s{1,3}?[^\s]+)*)\s*', line)

            if not name:
                self.lineProcessor = None
                return
            else:
                name = name.group(0)

            if name == "Forces":
                name = name + " Global"

            # Append empty force
            self.forceDict = dict()
            self.output[name] = self.forceDict

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

        nGroups = len(self.forceDict)

        nForceTypes = int(len(forceNames) / nGroups)

        # Append force names to dictionary
        for grId, groupName in enumerate(self.forceDict):
            forceGroupDic = self.forceDict[groupName]
            for fid in range(nForceTypes):
                forceGroupDic[forceNames[grId * nForceTypes + fid]] = dict()

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

        nGroups = len(self.forceDict)

        nForceTypes = len(values) / nGroups

        for grId, groupName in enumerate(self.forceDict):
            forceGroupDic = self.forceDict[groupName]
            for fid, forceName in enumerate(forceGroupDic):
                forceGroupDic[forceName][zoneName] = values[grId * nForceTypes + fid]

        if self.lastForce:
            self.lastForce = False
            self.lineProcessor = self.parseForceTitle

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


# class DirectoryParser:
#     def __init__(self, directoryPath, outputFile=None):
#         self.directory = directoryPath
#         if not outputFile:
#             self.output = self.directory + os.sep + "output.json"
#         else:
#             self.output = outputFile
#
#     def convert(self):
#         parsers = { "Log": LogParser(self.directory + os.sep + "fluent_log.log"),
#                     "FX": ForceParser(self.directory + os.sep + "FX"),
#                     "FY": ForceParser(self.directory + os.sep + "FY"),
#                     "FZ": ForceParser(self.directory + os.sep + "FZ"),
#                     "MX": ForceParser(self.directory + os.sep + "MX"),
#                     "MY": ForceParser(self.directory + os.sep + "MX"),
#                     "MZ": ForceParser(self.directory + os.sep + "MX"),
#                     "CoPy": ForceParser(self.directory + os.sep + "CoPy", singleForce=True),
#                     "CoPz": ForceParser(self.directory + os.sep + "CoPz", singleForce=True)}
#
#         resultDict = dict()
#
#         for name in parsers:
#             parser = parsers[name]
#             try:
#                 parser.parse()
#             except IOError:
#                 print "Parser " + name + " error.\nCouldn't open file " + os.path.basename(parser.path)
#             except Exception as e:
#                 print "Parser " + name + " error.\nCouldn't parse the " + os.path.basename(
#                     parser.path) + " file\n" + e.message + "\n"
#
#             if len(parser.output) != 0:
#                 resultDict[name] = parser.output

def writeCSV(fptr, titles, array2D):
    for name in titles[:-1]:
        fptr.write(name+",")
    fptr.write(titles[-1]+"\n")

    for rowId, row in enumerate(array2D):
        for element in row[:-1]:
            fptr.write(str(element)+",")
        newline = '\n'
        if rowId < len(array2D)-1:
            newline = ''
        fptr.write(str(row[-1]) + newline)

if __name__ == "__main__":

    baseDir = "specification/VISCID BLOCK - surowe"
    outFile = "output.json"

    resultDict = dict()

    parsers = {"Log": LogParser(baseDir + os.sep + "fluent_log.log"),
               "FX": ForceParser(baseDir + os.sep + "FX"),
               "FY": ForceParser(baseDir + os.sep + "FY"),
               "FZ": ForceParser(baseDir + os.sep + "FZ"),
               "MX": ForceParser(baseDir + os.sep + "MX"),
               "MY": ForceParser(baseDir + os.sep + "MY"),
               "MZ": ForceParser(baseDir + os.sep + "MZ"),
               "CoPy": ForceParser(baseDir + os.sep + "CoPy", singleForce=True),
               "CoPz": ForceParser(baseDir + os.sep + "CoPz", singleForce=True)}

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
            resultDict[name] = parser.output

    with open(outFile, "w") as filePtr:
        json.dump(resultDict, filePtr, indent=4)


    # Example of usage:
    mach = resultDict["Log"]["farFieldConditions"]["mach"]
    alpha = resultDict["Log"]["farFieldConditions"]["alpha"]

    cxGlobal, cyGlobal, czGlobal = resultDict["FX"]["Forces Global"]["Coefficients"]["Total"]["Net"]
    cmxGlobal, cmyGlobal, cmzGlobal = resultDict["MX"]["Moments - Moment Center (-1.1323 0 0)"]["Coefficients"]["Total"]["Net"]

    cxDV = resultDict["FX"]["Forces - Direction Vector (1 0 0)"]["Coefficients"]["Total"]["Net"]
    cyDV = resultDict["FY"]["Forces - Direction Vector (0 1 0)"]["Coefficients"]["Total"]["Net"]
    czDV = resultDict["FZ"]["Forces - Direction Vector (0 0 -1)"]["Coefficients"]["Total"]["Net"]

    cmxDV = resultDict["MX"]["Moments - Moment Center (-1.1323 0 0) Moment Axis (1 0 0)"]["Coefficients"]["Total"]["Net"]
    cmyDV = resultDict["MY"]["Moments - Moment Center (-1.1323 0 0) Moment Axis (0 1 0)"]["Coefficients"]["Total"]["Net"]
    cmzDV = resultDict["MZ"]["Moments - Moment Center (-1.1323 0 0) Moment Axis (0 0 1)"]["Coefficients"]["Total"]["Net"]

    titles = ['mach', 'alpha',
              'CX-global', 'CY-global', 'CZ-global', 'CMX-global', 'CMY-global', 'CMZ-global',
              'CX-dir', 'CY-dir', 'CZ-dir', 'CMX-dir', 'CMY-dir', 'CMZ-dir']
    data = [[mach, alpha,
            cxGlobal, cyGlobal, czGlobal, cmxGlobal, cmyGlobal, cmzGlobal,
            cxDV, cyDV, czDV, cmxDV, cmyDV, cmzDV]]

    with open("output.csv", "w") as f:
        writeCSV(f, titles, data)

