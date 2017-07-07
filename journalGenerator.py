






if __name__ == "__main__":

    import json, re, os

    setup = dict()

    with open("cases.json", 'r') as ptr:
        setup = json.load(ptr)

    #make directories:
    for name in setup:
        if not os.path.exists(name):
            os.makedirs(name)

    #Fill journal files
    files = {name: open(name+os.sep+name+".jou", 'w') for name in setup}

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