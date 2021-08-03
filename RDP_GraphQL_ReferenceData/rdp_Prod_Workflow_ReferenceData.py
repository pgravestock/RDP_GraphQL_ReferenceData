
# The purpose of this module is to:

#    o accept a csv list of identifiers, 
#    o send the identifiers to the Symbology APU and retrieve the corresponding Instrument PermID and Object Type
#    o sort the returned Instrumdent PermIDs into lists (one list per ObjectTyper) 
#    o select the appropriate reference data graphQL query for each objectType list and return the results as a json file.
 
# The script supports both Initialisation, and Delta queries - driven by the DeltaFlag an DeltaDate variables, DeltaFlag accepts
# values of Initialise or Delta. If the DeltaFlag variable is set to Delta, the DeltaDate variable must be populated with a date 
# in string format "yyyy-mm-ddT00:00:00z". If the DeltaFlag is set to Initialise, DeltaDate must be set to None.

# Based on the object type, and Initialise / Delta flag settings, the script will select a pre-defined graphQL file from 
# the ./gql_Queries directory, where presaved graphQL queries have been defined. These queries are all constructued to use
# query variables to pass the list of ObjectIDs, rather than injecting the list of IDs into the query text.

# Some instruments can be resolved into multiple objectTypes (common for Warrants/Structured Products and some bonds). The script 
# applies a hierarchy that will select the most appropriate ObjectType for this use case:

#    o If an instrument returns a SPInstrumet and EDInstrument objectType, use the SPInstrument objectType
#    o If an instrument returns a GovCorpInstrument and an EDInstrument objectType, use the GovCorpInstrument objectType.
#    o If an instrument returns a EDInstrumennt and a FundShareClass objectTyper, use the FundShareClass objectType.

# Note that this script runs against the Production RDP environment, and not all graphQL objectType queries are available in 
# production - currently only SPInstrument, GovCorpInstrument, and EDInstrument are supported.

# The script is able to accomodate the Symbology API limit of 1,500 identifiers per request (by sending multiple batches) and 
# also the graphQL API limit of 200 (max) objectIDs per request (by sending multiple batches). The graphQL batch sizes are configurable
# in this script as some queries (e.g. EDInstrument and GovCorpInstrument) that request AllQuotes for each instrument PermID can return
# large amounts of data that cause the API to timeout if the madimum 200 objectID per request limit is used. Trial and error shows that
# both EDInstrument and GovCorpInstrument will time out a batch sixze of >10 objectIDs is used.
 
# The script tracks the progess of all all API calls (Symbology and GraphQL) and writes a detailed log report in the ./Logs diretory a
# a json file, and a simpler csv file to allow the user to observe any errors that were returned by either Symbology or graphQL API. The log
# files allow the user to monitor overall performance of the different API calls, however it should be noted that the timers used to calculate 
# the run times are based on when the response has been downloaded to the users PC - in the case of large json response files, this can distort
# the reported run times vs actual run times on the APIs.
 
# The path / file name of the instrument list to be processed is stored in the Portfolio variable below. A selection of instrument lists of different
# object types and sizes can be founf in  ./Input. Note that the instrument lists must be formatted as a CSV file, with the first column identifying the 
# identifier type using the name type recognised by Symbology (e.g. Isin, Sedol, Cusip, ValorenNumber,Wpk, RIC). Any other identifier types will not be
# recognised. The symbology API request is designed to always return the Instrument PermID for the identifier provided.

# Version 1.01 An additional check is included when processing the Symbology output to stop an error from occuring
# when Symbology does not recognise an instrument identifer - prior to this change the code was looking for an  
# objectType that did not exist if the instrument was not recognsed, causing the code to fail.

import rdp_Common_Lib
import rdp_Prod_Serialise_List_To_Instrument_PermID
import rdp_Prod_Symbology_Post
import json
import csv

from datetime import datetime

SPInstrument=[]
GovCorpInstrument=[]
GovCorpQuote=[]
EDInstrument=[]
EdfQuote=[]
MuniInstrument=[]
AbsCmoInstrument=[]
FundShareClass=[]
MbsPoolInstrument=[]
MbsTbaInstrument=[]

Isin=[]
Cusip=[]
ValorenNumber=[]
Sedol=[]
RIC=[]
Wpk=[]

# The Instrument List being processed
Portfolio="./Input/Muni_Instrument_List_1000.csv"
DeltaFlag="Initialise"
DeltaDate=None

# This variable acts as a unique identifier that is embedded into all file outputs genrated when the script is run. The scrips generates
# the following files, so being able to determine which files are related to a specific run of the script is useful:

#    o the requests sent to Symbology - in multiple batches if the user is requesting more than 1,500 instruments
#    o the response from Symbology for the above requests
#    o the response of each graphQL query
#    o the json log file generated by this script that summarises the success or failire of each symbology and graphQL API call
#    o the csv log file that summarises the json log file

BatchIdentifier=datetime.now().strftime("%Y%m%d-%H%M%S")

# load the users portflio (instrument list) into a list
with open(Portfolio, mode='r', encoding='utf-8-sig') as f:
    reader=csv.reader(f)
    PortfolioIdentifiersList=list(reader)

#Break up the list into batches for Symbology - the recommended limit for Identifier to Insturment PermID requests is 1,500 identifiers per request.
BatchedPortfolio=rdp_Common_Lib.Chunk(PortfolioIdentifiersList,1500)

print(f"The Portfolio list of {len(PortfolioIdentifiersList)} records has been split into {len(BatchedPortfolio)} batches")

# These are the structures that will contain the symbology and graphQL logs to detail the run time of the entire request
RequestLog={}
ErrorsLog={}
SymbologySummary=[]
SymbologyBatchSummary=[]
GraphQLSummary=[]

#This is the outer loop for the batches of upto 1500 instruments to symbology
Li=0

#Generate lists of each Identifier type - Isin, Cusip, ValorenNumber, Sedol, RIC, Wpk

ValidObjectTypes=("GovCorpInstrument","GovCorpQuote", "FundShareClass","EDInstrument","AbsCmoInstrument","EdfQuote","FxirVehicle","MarketAttributableSource","organization","MuniInstrument","SPInstrument","MbsPoolInstrument","MbsTbaInstrument")
TotalSymbologyTimeStart=datetime.now()
while Li<len(BatchedPortfolio):
    #Build the objectType lists based on the BatchedPortfolio (a list of child lists, where each child list is 1,500 max identifiers)
    Isin, Cusip, ValorenNumber, Sedol, RIC, Wpk, Lei = rdp_Common_Lib.ProcessList(BatchedPortfolio[Li])
    SymbologyInput = rdp_Prod_Serialise_List_To_Instrument_PermID.ConvertObjectTypeList(Isin, Cusip, ValorenNumber, Sedol, RIC, Wpk, Lei, BatchIdentifier+"_"+str(Li))
    SymbologyBatchStartTime=datetime.now()

    #Pass the Synbology request to the API and retrieve the results
    SymbologyOutput, SymbologyRunTime, symbologyHttpStatus =rdp_Prod_Symbology_Post.symbology_v2_api(SymbologyInput,BatchIdentifier+"_"+str(Li))

    SymbologyBatchSummary.append({
        "symbologyBatch": Li,
        "symbologyBatchStartTime": str(SymbologyBatchStartTime),
        "symbologyApiBatchRunTime": SymbologyRunTime,
        "symbologyHttpStatus": symbologyHttpStatus
    })
    # Check to see if the sdymblogy API returned a valid response (http status 200)
    if symbologyHttpStatus==200:
        #There will only be a symbology payload to process if the http response code is 200. Anything else, and there is no payload to process.   

        #Sort the priority order for objectTypes for when symbology returns multiple objectTypes per identifier.
        objectTypeOrder=['SPInstrument', 'MuniInstrument', 'GovCorpInstrument', 'FundShareClass', 'EDInstrument','AbsCmoInstrument']
        order={key: i for i, key in enumerate(objectTypeOrder)}
        order
        {'EDInstrument': 5, 'FundShareClass': 4, 'MuniInstrument': 3, 'AbsCmoInstrument': 2, 'GovCorpInstrument': 1, 'SPInstrument': 0}

        SymbologyData= json.loads(SymbologyOutput)
        for sequence,payload in SymbologyData.items():
            if sequence=="data":
                instruments=SymbologyData['data']
                results=[] #This list will be built up with the fields being output in a single row for the resulting csv filer

                for instrument in instruments:
                    inputs=instrument['input']
                    for userInputs in inputs:
                        identifierType=userInputs['identifierType']
                        identifierValue=userInputs['value']
                        responses=instrument['output']

                        #Check if Symbology recognised the identifier
                        if len(responses)>0:
                    
                           # Check if Symbology returned multiple objectTypes
                            if len(responses)>1:
                        
                                # If multiple object types were returned, sort the list into the custom order defined in objectTypeOrder
                                # and take the first record only.
                                extracted_response=sorted(responses, key=lambda d: order[d['objectType']])[0]

                                objectType=extracted_response['objectType']
                                permID=extracted_response['value']
                                results.extend((identifierType, identifierValue, objectType, permID))

                            elif len(responses)==1:
                                extracted_response=responses[0]
                                objectType=extracted_response['objectType']
                                permID=extracted_response['value']
                                results.extend((identifierType, identifierValue, objectType, permID))

                            if objectType in ValidObjectTypes:
                                if objectType=="GovCorpQuote":
                                    GovCorpQuote.append(permID)
                            
                                elif objectType=="GovCorpInstrument":
                                    GovCorpInstrument.append(permID)

                                elif objectType=="FundShareClass":
                                    FundShareClass.append(permID)
                            
                                elif objectType=="EDInstrument":
                                    EDInstrument.append(permID)

                                elif objectType=="AbsCmoInstrument":
                                    AbsCmoInstrument.append(permID)

                                elif objectType=="EdfQuote":
                                    EdfQuote.append(permID)

                                elif objectType=="MuniInstrument":
                                    MuniInstrument.append(permID)

                                elif objectType=="SPInstrument":
                                    SPInstrument.append(permID)

                                elif objectType=="MbsPoolInstrument":
                                    MbsPoolInstrument.append(permID)

                                elif objectType=="MbsTbaInstrument":
                                    MbsTbaInstrument.append(permID)

                            else:
                                print(f"Unknown ObjectType {objectType} encountered. Please update code")                
        Li +=1
TotalSymbologyTimeEnd=datetime.now()
TotalSymbologyRunTime=(TotalSymbologyTimeEnd- TotalSymbologyTimeStart).total_seconds()

SymbologySummary.append({
    "totalIdentifiers": len(PortfolioIdentifiersList),
    "numberOfBatches": len(BatchedPortfolio),
    "totalSymbologyApiRunTime": TotalSymbologyRunTime,
    "symbologyBatches": SymbologyBatchSummary
})

print(f"Symbology Lookups Complete - {Li} batches")

#Now make the graphQL requests

#Batch Sizes for each query
GCChunkSize=10      #GovCorp Batch Size
AbsCmoChunkSize=10  #AbsCmo Batch Size
MuniChunkSize=100   #Muni Batch Size
EDChunkSize=10      #EDF Batch Size
OAChunkSize=200     #OrgAuthority Batch Size
SPChunkSize=200     #Structurted Product Batch Size
GCQChunkSize=200    #GovCorpQuote Batch Size
EDQChunkSize=200    #EdfQuote Batch Size
FSCChunkSize=200    #FundShareClass Batch Size

# GraphQL Query Paths. The queries used depends on whether the DeltaFlag is set to Initialise, in which case the
# standard grapghQL queries are defined. If the DeltaFlag is anything else, the Delta queries are used.
if DeltaFlag=="Initialise":
    #GovCorpInstrumentQuery="./gql_Queries/gql_GovCorp_Full_Instrument_and_All_Quotes_Reference_Data.gql"
    GovCorpInstrumentQuery="./gql_Queries/gql_GovCorp_Instrument_Summary_and_All_Quotes_Reference_Data.gql"
    GovCorpQuoteQuery="./gql_Queries/gql_End_Of_Day_Pricing.gql"
    MuniInstrumentQuery="./gql_Queries/gql_Muni_Full_ReferenceData.gql"
    EDInstrumentQuery="./gql_Queries/gql_Equity_Full_Reference_Data_All_Quotes_Query.gql"
    EDQuoteQuery="./gql_Queries/gql_End_Of_Day_Pricing.gql"
    OAQuery="./gql_Queries/gql_Organization_Full_Data_Query.gql"
    SPInstrumentQuery="./gql_Queries/gql_StructuredProduct_QuoteData.gql"
    print("Initialisation Queries selected")
else:
    GovCorpInstrumentQuery="./gql_Queries/gql_GovCorp_Full_Instrument_and_All_Quotes_Reference_Data_DELTA.gql"
    GovCorpQuoteQuery="./gql_Queries/gql_End_Of_Day_Pricing.gql"
    MuniInstrumentQuery="./gql_Queries/gql_Muni_Full_ReferenceData_No_Deal_TransferAgentID_DELTA.gql"
    EDInstrumentQuery="./gql_Queries/gql_Equity_Full_Reference_Data_All_Quotes_DELTA.gql"
    EDQuoteQuery="./gql_Queries/gql_End_Of_Day_Pricing.gql"
    OAQuery="./gql_Queries/gql_Organization_Full_Data_Query_DELTA.gql"
    SPInstrumentQuery="./gql_Queries/gql_StructuredProduct_Full_ReferenceData_DELTA.gql"
    print("Delta Queries selected")
    
if GovCorpInstrument:
    queryObjectType="GovCorpInstrument"
    graphQLLog = rdp_Common_Lib.SendGraphQLRequest(queryObjectType,DeltaFlag,DeltaDate,GCChunkSize,GovCorpInstrumentQuery,GovCorpInstrument,BatchIdentifier)
    for items in graphQLLog:
        objectType=items['objectType']
        objectCount=items['objectCount']
        chunkSize=items['chunkSize']
        totalGraphQLRunTimeForObjectType=items['totalGraphQLRunTimeForObjectType']
        graphQLBatches=items['batches']

    GraphQLSummary.append({
        "objectType": objectType,
        "objectCount": objectCount,
        "chunkSize": chunkSize,
        "totalGraphQLRunTimeForObjectType":totalGraphQLRunTimeForObjectType,
        "graphQLBatches": graphQLBatches
    })

if SPInstrument:
    queryObjectType="SPInstrument"
    graphQLLog= rdp_Common_Lib.SendGraphQLRequest(queryObjectType,DeltaFlag,DeltaDate,SPChunkSize,SPInstrumentQuery,SPInstrument,BatchIdentifier)

    for items in graphQLLog:
        objectType=items['objectType']
        objectCount=items['objectCount']
        chunkSize=items['chunkSize']
        totalGraphQLRunTimeForObjectType=items['totalGraphQLRunTimeForObjectType']
        graphQLBatches=items['batches']

    GraphQLSummary.append({
        "objectType": objectType,
        "objectCount": objectCount,
        "chunkSize": chunkSize,
        "totalGraphQLRunTimeForObjectType":totalGraphQLRunTimeForObjectType,
        "graphQLBatches": graphQLBatches
    })

if EDInstrument:
    queryObjectType="EDInstrument"
    graphQLLog=rdp_Common_Lib.SendGraphQLRequest(queryObjectType,DeltaFlag,DeltaDate,EDChunkSize,EDInstrumentQuery,EDInstrument,BatchIdentifier)

    for items in graphQLLog:
        objectType=items['objectType']
        objectCount=items['objectCount']
        chunkSize=items['chunkSize']
        totalGraphQLRunTimeForObjectType=items['totalGraphQLRunTimeForObjectType']
        graphQLBatches=items['batches']

    GraphQLSummary.append({
        "objectType": objectType,
        "objectCount": objectCount,
        "chunkSize": chunkSize,
        "totalGraphQLRunTimeForObjectType":totalGraphQLRunTimeForObjectType,
        "graphQLBatches": graphQLBatches
    })

if MuniInstrument:
    queryObjectType="MuniInstrument"
    graphQLLog=rdp_Common_Lib.SendGraphQLRequest(queryObjectType,DeltaFlag,DeltaDate,MuniChunkSize,MuniInstrumentQuery,MuniInstrument,BatchIdentifier)

    for items in graphQLLog:
        objectType=items['objectType']
        objectCount=items['objectCount']
        chunkSize=items['chunkSize']
        totalGraphQLRunTimeForObjectType=items['totalGraphQLRunTimeForObjectType']
        graphQLBatches=items['batches']

    GraphQLSummary.append({
        "objectType": objectType,
        "objectCount": objectCount,
        "chunkSize": chunkSize,
        "totalGraphQLRunTimeForObjectType":totalGraphQLRunTimeForObjectType,
        "graphQLBatches": graphQLBatches
    })

RequestLog['data']=[]
RequestLog['data'].append({
    "symbology": SymbologySummary,
    "graphQL": GraphQLSummary
})

OutputFile="./Logs/GraphQL_Log_"+ BatchIdentifier +".json"
print(f"Log output to : {OutputFile}\n")
with open(OutputFile,"w") as outFile:
    json.dump(RequestLog,outFile,indent=4)
outFile.close

rdp_Common_Lib.log_file_conversion(RequestLog, BatchIdentifier)

print(f"\nProcessing Complete - Check ./Logs for log details of this request, and ./Output for all output files.\n")
#====

