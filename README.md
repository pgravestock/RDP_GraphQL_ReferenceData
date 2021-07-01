# Introduction

The purpose of this module is to:

* accept a csv list of identifiers,
* send the identifiers to the Symbology APU and retrieve the corresponding Instrument PermID and Object Type
* sort the returned Instrumdent PermIDs into lists (one list per ObjectTyper)
* select the appropriate reference data graphQL query for each objectType list and return the results as a json file.

## Prerequisits

* An RDP account that is entitled to
  * run graphQL queries
  * Access PRS Reference Data
    * User credentials to be applied to the `rdp_Prod_Authentication_Token.py` file
* It is also assumed that the user has a working and stable Python Development Environment. The code uses the `requests` HTTP library in Python. If you have not added this library to your Python environment, you must add the requests module using the appropriate command from the command promp of your operating system. See <https://www.geeksforgeeks.org/how-to-install-requests-in-python-for-windows-linux-mac/> for details of how to install this module.

## Quick Start

* In the file `rdp_Prod_Workflow_ReferenceData.py` the variable `Portfolio` contains the path and file name of the instrument list that will be processed. The `./Input` directory contains a selection of different instrument lists of different sizes and objectTypes. Change the path/file name in the Portfolio variable to the instrument list that you want to run.
* Run this Python script. The terminal window will provide updates on the progress of the script as it processes the Instrument List, reporting on:
  * the number of identifiers recognised
  * the number of batches the instrument list is broken down to
  * the run time of each request to the Symbology API
  * the number of batches of ObjectIDs that are sent to the graphQL API for each objectType present in the instrument list.
  * the start time of each batch
  * the time taken to complete the graphQL request for each batch and the http status of the response
  * details of log files written to the `./Logs` directory
  * confirmation that processing is complete.

## Capabilities

### Initialise and Delta queries

The script supports both Initialisation, and Delta queries - driven by the DeltaFlag an DeltaDate variables, DeltaFlag accepts
values of `Initialise` or `Delta`. If the DeltaFlag variable is set to Delta, the DeltaDate variable must be populated with a date
in string format `yyyy-mm-ddT00:00:00z`. If the DeltaFlag is set to `Initialise`, DeltaDate must be set to `None`.

Based on the object type, and Initialise / Delta flag settings, the script will select a pre-defined graphQL file from
the ./gql_Queries directory, where presaved graphQL queries have been defined. These queries are all constructued to use
query variables to pass the list of ObjectIDs, rather than injecting the list of IDs into the query text.

### Downselecting Multiple ObjectTypes returned by Symbology

Some instruments can be resolved into multiple objectTypes (common for Warrants/Structured Products and some bonds). The script
applies a hierarchy that will select the most appropriate ObjectType for this use case:

* If an instrument returns a SPInstrumet and EDInstrument objectType, use the SPInstrument objectType
* If an instrument returns a GovCorpInstrument and an EDInstrument objectType, use the GovCorpInstrument objectType.
* If an instrument returns a EDInstrumennt and a FundShareClass objectTyper, use the FundShareClass objectType.

Note that this script runs against the Production RDP environment, and not all graphQL objectType queries are available in
production - currently only SPInstrument, GovCorpInstrument, and EDInstrument are supported.

### Autobatching of requests for Symbology and GraphQL APIs

The script is able to accomodate the Symbology API limit of 1,500 identifiers per request (by sending multiple batches) and
also the graphQL API limit of 200 (max) objectIDs per request (by sending multiple batches). The graphQL batch sizes are configurable
in this script as some queries (e.g. EDInstrument and GovCorpInstrument) that request AllQuotes for each instrument PermID can return
large amounts of data that cause the API to timeout if the madimum 200 objectID per request limit is used. Trial and error shows that
both EDInstrument and GovCorpInstrument will time out a batch sixze of >10 objectIDs is used.

### Logging of all API calls - Symbology and GraphQL

The script tracks the progess of all all API calls (Symbology and GraphQL) and writes a detailed log report in the ./Logs diretory a
a json file, and a simpler csv file to allow the user to observe any errors that were returned by either Symbology or graphQL API. The log
files allow the user to monitor overall performance of the different API calls, however it should be noted that the timers used to calculate
the run times are based on when the response has been downloaded to the users PC - in the case of large json response files, this can distort
the reported run times vs actual run times on the APIs.

The path / file name of the instrument list to be processed is stored in the Portfolio variable below. A selection of instrument lists of different
object types and sizes can be founf in  ./Input. Note that the instrument lists must be formatted as a CSV file, with the first column identifying the identifier type using the name type recognised by Symbology (e.g. Isin, Sedol, Cusip, ValorenNumber,Wpk, RIC). Any other identifier types will not be
recognised. The symbology API request is designed to always return the Instrument PermID for the identifier provided.
