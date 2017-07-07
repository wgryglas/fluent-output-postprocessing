

if __name__ == "__main__":
    import Parser
    import os, json

    os.chdir("specification")

    #find right directories:
    dirsToProcess = []
    for path in os.listdir("."):
        if os.path.isdir(path):
            files = os.listdir(path)
            ok = True
            for f in Parser.FILES.values():
                is_file_ok = f in files
                ok *= is_file_ok
            if ok:
                dirsToProcess.append(path)
                print "Accepting "+path
            else:
                print "WARNING! omitting directory "+path+" because there are missing files for proper postprocessing"

    # parse files, dump json version, collect data
    allDics = dict()
    for directory in dirsToProcess:
        parser = Parser.DirectoryParser(directory)
        parser.load()
        parser.dump(directory + os.sep + "output.json")
        allDics[os.path.basename(directory)] = parser.data



    #Dump json for all data in single location:
    with open("output.json", 'w') as f:
        json.dump(allDics, f, indent=4)

    # write CSV report
    colTitles = ""
    rows = []
    for dataName in allDics:
        data = allDics[dataName]
        colTitles, row = Parser.Data(data).table("Net")
        rows.append(row)

    with open("output.csv", 'w') as fptr:
        Parser.writeCSV(fptr, colTitles, rows)

