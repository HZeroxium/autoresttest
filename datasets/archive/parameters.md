Given a list of parameters and an API response schema, It's your responsibility to check how each parameter affects the API response schema.
You should ensure that the request parameters are valid and that the response adheres to the expected schema.
Determines how a property is affected by a query parameter or how a query parameter affects a response
Eg:  
- input.limit >= sizeOf(return)
- input.year == yearOfDay(return.date)
....
Returns a list of parameters and their reflection rules
[
{parameter: "limit", rule: input.limit >= sizeOf(return), reponse_property: null },
{parameter: "year ", rule: input.year == yearOfDay(return.date), reponse_property: date}
]
Here is list parameters and response schema
parameters:
- year (integer): A calendar year, minimum 2015, maximum 2031, default 2024.
- federal (string): A boolean parameter. If true or 1, will return only federal holidays. If false or 0, will return no federal holidays. values in one of [ "1", "0", "true", "false"]
- optional (string): A boolean parameter. If false or 0 (default), will return only legislated holidays. If true or 1, will return optional holidays for that region (if available). values in one of [ "1", "0", "true", "false"]
reponse schema: 
{
    "holidays": array of Holiday objects {
        "id": "(integer) Primary key for a holiday, minimum 1, maximum 32",
        "date": "(string) ISO date: the literal date of the holiday, format: date",
        "nameEn": "(string) English name",
        "nameFr": "(string) French name",
        "federal": "(integer) Whether this holiday is observed by federally-regulated industries, values in one of [ 1, 0 ]",
        "observedDate": "(string) ISO date: when this holiday is observed, format: date",
        "optional": "(integer) Whether this is a province-wide statutory holiday, or one that is optional for employers, format: binary values in one of [1]"
        "provinces": array of Province objects {
            "id": "(string) Canadian province abbreviations. values in one of [AB,BC,MB,NB,NL,NS,NT,NU,ON,PE,QC,SK,YT]"
            "nameFr": "(string) French name"
            "nameEn": "(string) English name"
            "sourceLink": "(string) URL to public holidays reference for this region, format: uri, pattern: https+",
            "sourceEn": "(string) Name of reference page with public holidays for this region"
            "optional": "(integer) Whether this province optionally observes a given holiday, format: binary, values in one of [1]",
            "nextHoliday": Holiday objects
            "holidays": array of Holiday objects
        }
    }
}