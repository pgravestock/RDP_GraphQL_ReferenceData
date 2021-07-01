#===============================================================================================================
# Refinitiv Data Platform demo app to return Symbology payload when using POST to request data for multiple ISINs
#===============================================================================================================
import requests
import json
import rdp_Prod_Authentication_Token
from datetime import datetime

def symbology_v2_api(Symbology_Input,IdentifierStamp):

    API_version = "/v1"
    #base_URL = "https://api.refinitiv.com/data/discovery/symbology/v1/lookup"
    base_URL = "https://api.refinitiv.com"

    category_URL = "/discovery/symbology"
    endpoint_URL = "/lookup"

    RESOURCE_ENDPOINT = base_URL + category_URL + API_version + endpoint_URL
    

    #=================================================

    # Get the latest access token
    #print("Getting OAuth access token....")
    accessToken=rdp_Prod_Authentication_Token.getToken()
    #print("Lookup Instruments")

    headerData = {"Authorization" : "Bearer " + accessToken, "content-type" : "application/json"}

    StartTime=datetime.now()

    dResp = requests.post(RESOURCE_ENDPOINT, headers= headerData, data=Symbology_Input)

    EndTime=datetime.now()
    if dResp.status_code !=200:
        print("There was a problem. Code %s, Message: %s" % (dResp.status_code, dResp.text))
        jResp=dResp.text
    else:
        print(f"Response from Symnbology API complete, results stored in: ./Output/Symbology_Output_" + IdentifierStamp + ".json\n")
        jResp=json.loads(dResp.text)

        with open("./Output/Symbology_Output_" + IdentifierStamp + ".json","w") as outFile:
            json.dump(jResp,outFile,indent=4)
        outFile.close
    SymbologyRunTime= (EndTime - StartTime).total_seconds()
    print(f"Symbology API Run Time: {SymbologyRunTime}")
    
    return json.dumps(jResp,indent=4), SymbologyRunTime, dResp.status_code
    
#====================================

