#! /usr/bin/python

import os
import re
import json

"""
Saving convention:
variable : value

Variables descriptions:
case - the case name obtained from the fluent journal file. The file name can contain white spaces
nIteration - number of iteration read form the fluent file
residualNames - residual names array
residualValues - corresponding residual values array
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
            #fh.seek(file_size - offset)
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

    def parse(self):

        line = ""
        with open(self.path, "r") as f:
            while line.isspace() or 0 == len(line):
                line = f.readline()

        result = re.search(r'-i\s*([\w\s*]+)\.jou', line)
        if not result:
            raise Exception("The line: "+line[:-1]+"\ndoes not contain -i ....jou sentence required to obtain case name")

        caseName = result.groups(0)[0]

        #---------------------------------------------------------------------------------------------------------------

        lineBuffer = []
        residualsMatcher = re.compile(r'\s*iter\s*')

        residualLine = ""

        for line in ropen(self.path):
            if residualsMatcher.match(line):
                residualLine = line
                break
            else:
                lineBuffer.append(line)

        residualNames=re.split(r'\s+', residualLine.strip())

        residualValues=[]
        for line in lineBuffer[-1::-1]:
            tmp = re.split(r'\s+', line.strip())

            if len(tmp) != len(residualNames) + 1:
                break

            residualValues = tmp

        nIter = int(residualValues[0])

        residualNames = residualNames[1:-1]
        residualValues = map(float, residualValues[1:-2])

        return {"case": caseName,
                "nIteration": nIter,
                "residualNames": residualNames,
                "residualValues": residualValues}


class ForceParser:
    def __init__(self, path):
        self.path = path

        self.titles = []
        self.tableNames = []
        self.lineProcessor = self.parseTitle

    def parseTitle(self, line):

        print "line:", line

        res = re.search(r'\s*^"([a-z-A-Z]+)^"\s*', line)

        if res:
            print "force name:", res.group(0)[0]
            self.titles.append(res.group(0)[0])
            self.lineProcessor = self.parseTableNames
        # else:
        #     raise Exception("Could not read the force title name")


    def parseTableNames(self, line):
        self.lineProcessor = None

    def parse(self):

        with open(self.path, "r") as fptr:
            line=""
            for line in fptr:
                if self.lineProcessor is not None:
                    break

                self.lineProcessor(line)










if __name__ == "__main__":

    baseDir = "specification/VISCID BLOCK - surowe"
    outFile = "output.json"

    resultDict = dict()

    parsers = {"fluent log": LogParser(baseDir + os.sep + "fluent_log.log"),
               "FX": ForceParser(baseDir + os.sep + "FX")}

    for name in parsers:
        parser = parsers[name]
        try:
            resultDict.update(parser.parse())
        except Exception as e:
            print "Parser "+name+" error.\nCouldn't parse the " + os.path.basename(parser.path) + " file\n"+e.message+"\n"

    with open(outFile, "w") as filePtr:
        json.dump(resultDict, filePtr, indent=2)




