




"""
Generate fluent cases basing on the cases.json and template.jou files.
Each template varaible in the tmeplate.jou need to be defined in the cases.json.

{
  "test_case_1":
  {
    "Mach": [0.1, 0.2, 0.4],
    "DIRX": "1:0.1:2",
    "DIRY": 0.1,
    "DIRZ": 0.0,
	"MOMC": "0.0, 0.0, 0.0"
  },
  "test_case_2":
  {
    "Mach": 1.5,
    "DIRX": 0.9,
    "DIRY": 0.1,
    "DIRZ": 0.0,
	"MOMC": "0.0, 0.0, 0.0"
  }
}

If the variable is has value [...] it means that the variable will be placed multiple times - the group named e. g.
"test_case_1" will be repeated as many times as long is the list. Each generated case will be named with group name prefix:
 "test_case_1" plus suffix indicating case grop number, in this case it would be: "test_case_1_0", "test_case_1_1", "test_case_1_2"

The text in the variable looking like number:number:number indicates linear space of values. In above example
  the "DIRX" variable has value "1:0.1:2", what would be translated as list of subsequent numbers with step equal to 0.1
  - [1, 1.1, 1.2, 1.3, 1.4, 1.5,  1.6, 1.7, 1.8, 1.9, 2]. This list, of length 11 elements would result also in 9 cases.

  Together with 3 values of "Mach" variable list the total number of generated cases for above example
  would be equal 3 * 11 = 33 cases.
"""

if __name__ == "__main__":

    import json, re, os

    setup = dict()

    with open("cases.json", 'r') as ptr:
        setup = json.load(ptr)

    linspaceReg = re.compile(r'\b(\S+)\b:\b(\S+)\b:\b(\S+)\b')

    for name in setup:
        case = setup[name]
        nvars = []
        for variable in case:
            if isinstance(case[variable], list):
                nvars.append(len(case[variable]))
            elif isinstance(case[variable], unicode):
                res = linspaceReg.search(str(case[variable]))
                if res:
                    start = float(res.group(1))
                    step = float(res.group(2))
                    end = float(res.group(3))
                    values = []
                    nvals = int((end-start)/step) + 1
                    for i in range(nvals):
                        values.append(start + i*step)

                    case[variable] = values
                    nvars.append(len(values))
                else:
                    nvars.append(1)
                    case[variable] = [case[variable]]
            else:
                nvars.append(1)
                case[variable] = [case[variable]]

        case["num_cases"] = reduce(lambda a, b: a*b, nvars, 1)


    setupExpaned = dict()

    for name in setup:

        if setup[name]["num_cases"] == 1:
            setupExpaned[name] = dict()
            for varname in setup[name]:
                if varname != "num_cases":
                    setupExpaned[name][varname] = setup[name][varname][0] #convert created lists to single values
            continue

        ncases = setup[name]["num_cases"]

        for num in range(setup[name]["num_cases"]):
                newName = name + "_" + str(num)
                setupExpaned[newName] = dict()


        # Now generate loops in the loops inside single while :)
        varNames = [varname for varname in setup[name] if varname != "num_cases"]
        levelNames = {i: varname for i, varname in enumerate(varNames)}
        levelPosition = [0 for i in range(len(varNames))]
        levelMaxPositions = [len(setup[name][varname]) for varname in varNames]
        caseId = 0
        level = 0
        endLevel = len(varNames)
        while caseId < ncases:
            caseName = name + "_" + str(caseId)
            setupExpaned[caseName][levelNames[level]] = setup[name][levelNames[level]][levelPosition[level]]

            if level == endLevel-1:
                levelPosition[level] += 1

            if levelPosition[level] == levelMaxPositions[level]: # and level > 0 it should never happend due to while limit

                toDecrease = level-1

                while toDecrease > 0:
                    if levelPosition[toDecrease] + 1 < levelMaxPositions[toDecrease]:
                        levelPosition[toDecrease] += 1
                        toDecrease = 0
                    else:
                        levelPosition[toDecrease] = 0
                        toDecrease -= 1

                levelPosition[level] = 0

            level += 1
            if level == endLevel:
                caseId += 1
                level = 0

    setup = setupExpaned

    #make directories:
    for name in setup:
        if not os.path.exists(name):
            os.makedirs(name)

    #Fill journal files
    files = {name: open(name+os.sep+name+".jou", 'w') for name in setup}

    #Dump json setup:
    for name in setup:
        with open(name+os.sep+"case.json", 'w') as f:
            json.dump(setup[name], f, indent=4)

    varnameRegex = re.compile(r'\b(TEMPLATE_(\S+))\b')

    with open("template.jou", 'r') as template:
        for line in template.readlines():
            res = varnameRegex.findall(line)
            if len(res) > 0:
                toWrite = line
                for case in setup:
                    for var in res:
                        value = setup[case][var[1]]
                        toWrite = re.sub(var[0], str(value), toWrite)
                    files[case].write(toWrite)

            else:
                for f in files.values():
                    f.write(line)

    for f in files.values():
        f.close()