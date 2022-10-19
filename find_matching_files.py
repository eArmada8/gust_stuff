# Used to find matching files from one directory in another directory
# Developed to find raw 3DMigoto buffers from frame dumps
# GitHub eArmada8/gust_stuff
import os, glob, zlib

def generate_hashlist(pathfilter):
    # Make a list of all matching files, recursively
    filelist = glob.glob(pathfilter,recursive=True)
    hashlist = []
    for i in range(len(filelist)):
        filehash = {}
        filehash['filename'] = filelist[i]
        with open(filelist[i], 'rb') as f:
            filehash['filehash'] = hex(zlib.crc32(f.read()))
        hashlist.append(filehash)
    return(hashlist)

def find_matches(hash,search_results):
    return [x for x in search_results if x['filehash'] == hash]

def generate_resultlist(sourcepathfilter,searchpathfilter):
    sourcehashes = generate_hashlist(sourcepathfilter)
    searchhashes = generate_hashlist(searchpathfilter)
    output = "Matches:\r\n\r\n"
    for i in range(len(sourcehashes)):
        output = output + "Source: " + sourcehashes[i]['filename'] + "\r\n"
        matches = find_matches(sourcehashes[i]['filehash'], searchhashes)
        if len(matches) > 0:
            for j in range(len(matches)):
                output = output + matches[j]['filename'] + "\r\n"
    return(output)

if __name__ == "__main__":
    os.chdir(os.path.abspath(os.path.dirname(__file__)))

    sourcepath = str(input("Please enter the directory for source files:  ")).replace('\\','/')
    filter = str(input("Please enter the file search terms: [e.g. *.ib]  "))
    sourcepathfilter = (sourcepath + '/' + filter).replace('//','/')
    searchpath = str(input("Please enter the directory to search for matches:  ")).replace('\\','/')
    searchpathfilter = (searchpath + '/' + '*').replace('//','/')

    with open('search_results.txt','w') as f_out:
        result = f_out.write(generate_resultlist(sourcepathfilter,searchpathfilter))