from datetime import datetime
import json
import requests
import rdp_Prod_Authentication_Token
import os
import csv
from csv import writer


# This function takes a list - OriginalList, and breaks it into chunks specified by Size. It is used to split the ObjectID lists 
# generated when the output from a Symbollogy request is processed into the chunks of 'Size' defined by the scipt that generates
# the graphQL request. Depending on the graphQL quey being used, it is necessary to break the requests into chunks less than the
# platform limit of 200 objects per graphQL request. 
def Chunk (OriginalList, Size):

    ChunkedList=[]
    ChunkedList=[OriginalList[i:i+Size] for i in range(0,len(OriginalList),Size)]

    return ChunkedList

#=======

# This function accepts the file path/name of a .json file, opens the file, and reads the file into an object that is
# then returned back to the script that called this function. Its main use is to load a graphQL query into an object so that it
# can then be sent to the graphQL API.     
def loadQuery(graphQLQueryFile):
    fileobj=open(graphQLQueryFile)
    outstr=fileobj.read()
    fileobj.close()

    return outstr

#=======

def graphQLRequest(graphQLQuery,queryType, Seq, IdentifierStamp):

    EDP_version = "/v1"
    base_URL = "https://api.refinitiv.com"
    category_URL = "/data-store"
    endpoint_URL = "/graphql"
    CLIENT_SECRET = ""

    SCOPE = "trapi"

    RESOURCE_ENDPOINT = base_URL + category_URL + EDP_version + endpoint_URL
    #print (f"\nAPI Endpoint: {RESOURCE_ENDPOINT}")

    #key=".json"
    #baseLoc=fileObject.find(key)
    outputfile='./Output/'+queryType+'_' + str(Seq) + '_Response_'+ IdentifierStamp + '.json'

    #=================================================
    # Get the latest access token
    #print("Getting OAuth access token....")
    accessToken=rdp_Prod_Authentication_Token.getToken()
    #print("Lookup ReferenceData")

    headerData = {"Authorization" : "Bearer " + accessToken, "content-type" : "application/json"}
    
    dResp = requests.post(RESOURCE_ENDPOINT, headers= headerData, data=graphQLQuery)

    if dResp.status_code !=200:
        print("There was a problem. Code %s, Message: %s" % (dResp.status_code, dResp.text))
        jResp=dResp.text
        GraphQLResponse=open(outputfile,"w")
        GraphQLResponse.write(json.dumps(jResp,indent=4))
        GraphQLResponse.close()
        file_size=os.path.getsize(outputfile)
    else:
        jResp=json.loads(dResp.text)
        GraphQLResponse=open(outputfile,"w")
        GraphQLResponse.write(json.dumps(jResp,indent=4))
        GraphQLResponse.close()
        file_size=os.path.getsize(outputfile)
        code=dResp.status_code
        
    return jResp, file_size, dResp.status_code


#=====================================================

def SendGraphQLRequest(queryObjectType, QueryType, DeltaDate, ChunkSize, GQLQuery, InstrumentList, IdentifierStamp):
    # v1.0.1 Changed Json object name that contains list of objectIDs in batch with errors to match the object name
    # used in the graphql query to make it easier to paste list of objectIDs into a manual query.
    # v1.0.2 Changed paramater name from DeltaFlag to QueryType to make its name more representative
    ChunkedInstrumentList=[]
    ChunkedInstrumentList=Chunk(InstrumentList,ChunkSize)
    print(f"There are {len(InstrumentList)} {queryObjectType}s split into {len(ChunkedInstrumentList)} batches")

    StartTotalTime=datetime.now()
    Bi=0
    gqlBatchDetails=[]
    batchErrors=[]
    gqlBatchSummary=[]
    # Step through each batch of objectIDs and run the supplied graphQL query
    while Bi<len(ChunkedInstrumentList):

        GraphQLQuery={}
        # Load the supplied query into this dictionary
        GraphQLQuery['query']=loadQuery(GQLQuery)

        if QueryType=="Delta":
            GraphQLQuery['variables']={
                "ObjectList":ChunkedInstrumentList[Bi],
                "DeltaDate":DeltaDate
            }
        elif QueryType=="Initialise":
            GraphQLQuery['variables']={
                "ObjectList":ChunkedInstrumentList[Bi]
            }
        elif QueryType=="Pricing":
            GraphQLQuery['variables']={
                "ObjectList":ChunkedInstrumentList[Bi],
                "PriceDate":DeltaDate
            }
        # Load the combined query into a json structure
        CompiledQuery=json.dumps(GraphQLQuery)

        BatchStartTime=datetime.now()
        print(f"{queryObjectType} batch {Bi} Start at {BatchStartTime} seconds")        
        gqlResponse, fileSize, httpStatus = graphQLRequest(CompiledQuery,queryObjectType,Bi, IdentifierStamp)
        BatchEndTime=datetime.now()
        BatchRunTime=(BatchEndTime-BatchStartTime).total_seconds()
        print(f"{queryObjectType} batch {Bi} complete in {BatchRunTime} seconds, http status:{httpStatus}\n")

        # First check if the API responded correctly.
        if httpStatus != 200:
            # The API did not respond as expected
            message=gqlResponse
            batchStatus="API_Fail"
        else:
            batchStatus=None
            for sequence, payload in gqlResponse.items():
                if sequence=="errors":
                    errors=gqlResponse['errors']
                    errorInfo=errors[0]
                    message=errorInfo['message']
                    extensions=errorInfo['extensions']
                    batchErrorCode=extensions['errorCode']
                    batchStatus="Fail"
        
                if batchStatus!="Fail":
                    batchStatus="Success"
                    batchErrorCode=None

        if batchStatus=="Success":
            gqlBatchDetails.append({
                "batch": Bi,
                "batchStartTime": str(BatchStartTime),
                "batchGraphQLRunTime": BatchRunTime,
                "batchHttpStatus": httpStatus,
                "batchStatus": batchStatus,
                "batchErrorCode": batchErrorCode,
                "fileSize": fileSize,
                "objectCount":len(ChunkedInstrumentList[Bi])
            })
        elif batchStatus=="API_Fail":
            gqlBatchDetails.append({
                "batch":Bi,
                "batchStartTime": str(BatchStartTime),
                "batchGraphQLRunTime": BatchRunTime,
                "batchHttpStatus": httpStatus,
                "batchStatus": batchStatus,
                "batchErrorCode": batchErrorCode,
                "batchErrorMessage": message,
                "batchExtensions": "",
                "fileSize": fileSize,
                "objectCount": len(ChunkedInstrumentList[Bi]),
                "ObjectList": ChunkedInstrumentList[Bi]
            })
        else:
            gqlBatchDetails.append({
                "batch":Bi,
                "batchStartTime": str(BatchStartTime),
                "batchGraphQLRunTime": BatchRunTime,
                "batchHttpStatus": httpStatus,
                "batchStatus": batchStatus,
                "batchErrorCode": batchErrorCode,
                "batchErrorMessage": message,
                "batchExtensions": extensions,
                "fileSize": fileSize,
                "objectCount": len(ChunkedInstrumentList[Bi]),
                "ObjectList": ChunkedInstrumentList[Bi]
            })
        
        batchStatus=None

        Bi += 1
    
    EndTotalTime=datetime.now()
    gqlBatchSummary.append({
        "objectType": queryObjectType,
        "objectCount": len(InstrumentList),
        "chunkSize": ChunkSize,
        "totalGraphQLRunTimeForObjectType": (EndTotalTime-StartTotalTime).total_seconds(),
        "batches": gqlBatchDetails
    })
    print(f"{queryObjectType} processing complete in {(EndTotalTime-StartTotalTime).total_seconds()}\n")
    return gqlBatchSummary

#=======

# This function accepts the json output that is generated when a users graphQL request has been fully processed, and generates
# a csv file that lists the batch details that are included in the json log report. The output is saved in the ./Logs directory

def log_file_conversion(JsonObject,IdentifierStamp):
    
    outputFile="./Logs/Summary_" + IdentifierStamp+".csv"
    logcsv=open(outputFile, 'w')
    logline=[]
    
    for key,value in JsonObject.items():

        if key=="data":
            logContents=JsonObject['data']
            for logContent in logContents:
                for logSubContent in logContent:
                    if logSubContent=="symbology":
                        symbologyLog=logContent['symbology']
                        logcsv.write("SymbologySummary\n")
                        logcsv.write("totalIdentifiers,numberOfBatches,totalSymbologyApiRunTime\n")
                        for items in symbologyLog:
                            totalIdentifiers=items['totalIdentifiers']
                            numberOfBatches=items['numberOfBatches']
                            totalSymbologyApiRunTime=items['totalSymbologyApiRunTime']

                            logline.extend((totalIdentifiers, numberOfBatches, totalSymbologyApiRunTime))
                            wr=csv.writer(logcsv,dialect='excel')
                            wr.writerow(logline)
                            logline=[]

                            symbologyBatches=items['symbologyBatches']
                            logcsv.write("symbologyBatch,symbologyBatchStartTime,symbologyApiBatchRunTime,symbologyHttpStatus\n")
                            for symbologyBatchDetails in symbologyBatches:
                                symbologyBatch=symbologyBatchDetails['symbologyBatch']
                                symbologyBatchStartTime=symbologyBatchDetails['symbologyBatchStartTime']
                                symbologyApiBatchRunTime=symbologyBatchDetails['symbologyApiBatchRunTime']
                                symbologyHttpStatus=symbologyBatchDetails['symbologyHttpStatus']

                                logline.extend((symbologyBatch, symbologyBatchStartTime, symbologyApiBatchRunTime, symbologyHttpStatus))
                                wr=csv.writer(logcsv,dialect='excel')
                                wr.writerow(logline)
                                logline=[]

                    elif logSubContent=="graphQL":
                        graphQlLog=logContent['graphQL']
                        logcsv.write("GraphQLSummary\n")
                        logcsv.write("objectType,objectCount,chunkSize, totalObjectTypeGraphQLApiRunTime\n")
                        for items in graphQlLog:
                            objectType=items['objectType']
                            objectCount=items['objectCount']
                            chunkSize=items['chunkSize']
                            totalGraphQLRunTimeForObjectType=items['totalGraphQLRunTimeForObjectType']

                            logline.extend((objectType, objectCount, chunkSize,totalGraphQLRunTimeForObjectType))
                            wr=csv.writer(logcsv,dialect='excel')
                            wr.writerow(logline)
                            logline=[]

                            graphQLBatches=items['graphQLBatches']
                            logcsv.write("objectType,batch,batchStartTime,batchGraphQLRunTime,batchHttpStatus,batchStatus,batchErrorCode,fileSize,objectCount\n")
                            for graphQLBatchDetails in graphQLBatches:
                                batch=graphQLBatchDetails['batch']
                                batchStartTime=graphQLBatchDetails['batchStartTime']
                                batchGraphQLRunTime=graphQLBatchDetails['batchGraphQLRunTime']
                                batchHttpStatus=graphQLBatchDetails['batchHttpStatus']
                                batchStatus=graphQLBatchDetails['batchStatus']
                                batchErrorCode=graphQLBatchDetails['batchErrorCode']
                                fileSize=graphQLBatchDetails['fileSize']
                                objectCount=graphQLBatchDetails['objectCount']

                                logline.extend((objectType, batch, batchStartTime, batchGraphQLRunTime, batchHttpStatus, batchStatus, batchErrorCode, fileSize, objectCount))
                                wr=csv.writer(logcsv,dialect='excel')
                                wr.writerow(logline)
                                logline=[]
       
    logcsv.close()
    print(f"\n\nLog File {outputFile} Done")
                    
#=======

def ProcessList(ListObject):
    print(f"\n\n")
    #This List (tuple) contains the accepted Identifier Types. When processing the input file, if an identifier type is found that is not in this list, the row will be skipped
    #and the user notified
    validIdentifiers=("Isin","Cusip","ValorenNumber", "Sedol", "RIC", "Wpk", "Lei")
    
    #Lists that will store identifiers of each recognised identifier type
    Isin=[]
    Cusip=[]
    ValorenNumber=[]
    Sedol=[]
    RIC=[]
    Wpk=[]
    Lei=[]

    line_count = 0
    error_count = 0
    for row in ListObject:
        if row[0] in validIdentifiers:
            line_count += 1
            if row[0]=="Isin":
                Isin.append(row[1])
            elif row[0]=="Cusip":
                Cusip.append(row[1])
            elif row[0]=='ValorenNumber':
                ValorenNumber.append(row[1])
            elif row[0]=="Sedol":
                Sedol.append(row[1])
            elif row[0]=="RIC":
                RIC.append(row[1])
            elif row[0]=="Wpk":
                Wpk.append(row[1])
            elif row[0]=="Lei":
                Lei.append(row[1])
        
        else:
            print(f"Unrecognised identifier type  {row[0]} {row[1]}")
            error_count += 1
    return Isin, Cusip, ValorenNumber, Sedol, RIC, Wpk, Lei

def ProcessOrganizationList(ListObject):
    print(f"\n\n")
    #This List (tuple) contains the accepted Identifier Types. When processing the input file, if an identifier type is found that is not in this list, the row will be skipped
    #and the user notified
    validIdentifiers=("Lei")
    
    #Lists that will store identifiers of each recognised identifier type

    Lei=[]

    line_count = 0
    error_count = 0
    for row in ListObject:
        if row[0] in validIdentifiers:
            line_count += 1
            if row[0]=="Lei":
                Lei.append(row[1])
        
        else:
            print(f"Unrecognised identifier type  {row[0]} {row[1]}")
            error_count += 1
    return Lei
