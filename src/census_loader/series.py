# fmt: off
"""
Census Bureau API — Series & Geography Config
===============================================

Config-driven catalog for a Census API loader.  Every entry stores
exactly what the client needs to build a call like:

    data = c.acs5.get(series.variables, {**geo, **series.predicates})

Hierarchy (same pattern as the FRED catalog):

    Subcategory:  from census_series import AGE_SEX, RACE, HOUSEHOLD_INCOME
    Category:     from census_series import DEMOGRAPHICS, INCOME_POVERTY
    Everything:   from census_series import ALL_SERIES

Tuple schema
------------
Each value is a 3-tuple:

    ("Friendly_Name",            # human-readable label
     "dataset_method",           # maps to client attr: acs5, acs1, pep, sf1 …
     (<variables>),              # tuple of var codes to pass in `get`
    )

If a whole table group is wanted, store it as the string "group(BXXXXX)".
The loader can detect the string vs tuple and branch accordingly.

Optional predicates (SAHIE income-to-poverty ratio, PEP age/sex/race
filters) live in PREDICATES at the bottom — keeps the main dicts lean.
"""


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  FIPS STATE CODES                                                       ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

FIPS_STATES = {
    "01": "Alabama",        "02": "Alaska",         "04": "Arizona",
    "05": "Arkansas",       "06": "California",     "08": "Colorado",
    "09": "Connecticut",    "10": "Delaware",       "11": "District of Columbia",
    "12": "Florida",        "13": "Georgia",        "15": "Hawaii",
    "16": "Idaho",          "17": "Illinois",       "18": "Indiana",
    "19": "Iowa",           "20": "Kansas",         "21": "Kentucky",
    "22": "Louisiana",      "23": "Maine",          "24": "Maryland",
    "25": "Massachusetts",  "26": "Michigan",       "27": "Minnesota",
    "28": "Mississippi",    "29": "Missouri",       "30": "Montana",
    "31": "Nebraska",       "32": "Nevada",         "33": "New Hampshire",
    "34": "New Jersey",     "35": "New Mexico",     "36": "New York",
    "37": "North Carolina", "38": "North Dakota",   "39": "Ohio",
    "40": "Oklahoma",       "41": "Oregon",         "42": "Pennsylvania",
    "44": "Rhode Island",   "45": "South Carolina", "46": "South Dakota",
    "47": "Tennessee",      "48": "Texas",          "49": "Utah",
    "50": "Vermont",        "51": "Virginia",       "53": "Washington",
    "54": "West Virginia",  "55": "Wisconsin",      "56": "Wyoming",
    "72": "Puerto Rico",
}

# Reverse lookup:  "California" → "06"
STATE_FIPS = {v: k for k, v in FIPS_STATES.items()}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  GEOGRAPHY LEVELS                                                       ║
# ╚═══════════════════════════════════════════════════════════════════════════╝
#
# Predicate fragments the loader can plug into the `for` / `in` dict.
# Finest → coarsest.  Each dict is a ready-made geo kwarg.

GEO = {
    # ── ACS 5-Year (finest available) ─────────────────────────────────────
    "block_group_in_state":  {"for": "block group:*",
                              "in": "state:{st}&in=county:{co}&in=tract:{tr}"},
    "tract_in_state":        {"for": "tract:*",              "in": "state:{st}"},
    "tract_in_county":       {"for": "tract:*",              "in": "state:{st}&in=county:{co}"},
    "county_in_state":       {"for": "county:*",             "in": "state:{st}"},
    "county_all":            {"for": "county:*"},
    "place_in_state":        {"for": "place:*",              "in": "state:{st}"},
    "place_all":             {"for": "place:*"},
    "msa_all":               {"for": "metropolitan statistical area/micropolitan statistical area:*"},
    "congressional_district":{"for": "congressional district:*", "in": "state:{st}"},
    "zcta_all":              {"for": "zip code tabulation area:*"},
    "state_all":             {"for": "state:*"},
    "us":                    {"for": "us:1"},
    # ── SAIPE (county + school district) ──────────────────────────────────
    "school_district_in_state": {"for": "school district (unified):*", "in": "state:{st}"},
}

# Which datasets support which geo levels (finest available)
DATASET_GEO_DEPTH = {
    "acs5":          "block_group",           # ACS 5-Year Detailed Tables
    "acs5/subject":  "tract",                 # ACS 5-Year Subject Tables
    "acs5/profile":  "tract",                 # ACS 5-Year Data Profiles
    "acs1":          "place",                 # ACS 1-Year (65k+ pop only)
    "pep":           "county",                # Population Estimates
    "saipe":         "county",                # + school district via /schdist
    "sahie":         "county",                # Small Area Health Insurance
    "dec/dhc":       "block",                 # Decennial Demographic & Housing
    "dec/pl":        "block",                 # Decennial Redistricting (P.L. 94-171)
    "cbp":           "zipcode",               # County Business Patterns
}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  POPULATION & AGE                                                       ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

TOTAL_POPULATION = {
    "TOTAL_POP":            ("Total_Population", "acs5",
                             ("B01003_001E",)),
    "POP_BY_AGE_SEX":       ("Population_By_Age_Sex", "acs5",
                             "group(B01001)"),                         # 49 vars: male/female × age buckets
    "MEDIAN_AGE":           ("Median_Age", "acs5",
                             ("B01002_001E",)),                        # overall
    "MEDIAN_AGE_MALE":      ("Median_Age_Male", "acs5",
                             ("B01002_002E",)),
    "MEDIAN_AGE_FEMALE":    ("Median_Age_Female", "acs5",
                             ("B01002_003E",)),
    "POP_UNDER_5":          ("Pop_Under_5", "acs5",
                             ("B01001_003E", "B01001_027E")),          # male + female under 5
    "POP_UNDER_18":         ("Pop_Under_18", "acs5",
                             ("B09001_001E",)),                        # children table
    "POP_65_PLUS":          ("Pop_65_And_Over", "acs5",
                             ("B01001_020E", "B01001_021E", "B01001_022E",
                              "B01001_023E", "B01001_024E", "B01001_025E",
                              "B01001_044E", "B01001_045E", "B01001_046E",
                              "B01001_047E", "B01001_048E", "B01001_049E")),
    "DEPENDENCY_RATIO":     ("Age_Dependency_Ratio", "acs5/subject",
                             ("S0101_C01_001E", "S0101_C01_022E",      # total, under 18
                              "S0101_C01_030E")),                      # 65+
}

AGE_DETAIL = {
    "AGE_GROUPS_5YR":       ("Age_5yr_Groups_Full", "acs5",
                             "group(B01001)"),
    "AGE_PROFILE":          ("Age_Sex_Profile", "acs5/subject",
                             "group(S0101)"),                          # subject table with %s
    "SCHOOL_AGE_5_17":      ("School_Age_Pop_5_17", "acs5",
                             ("B01001_004E", "B01001_005E", "B01001_006E",
                              "B01001_028E", "B01001_029E", "B01001_030E")),
    "WORKING_AGE_25_64":    ("Working_Age_Pop_25_64", "acs5/subject",
                             ("S0101_C01_025E", "S0101_C01_026E",
                              "S0101_C01_027E", "S0101_C01_028E")),
}

POPULATION = {**TOTAL_POPULATION, **AGE_DETAIL}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  RACE & ETHNICITY                                                       ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

RACE = {
    "RACE_TOTAL":           ("Race_All_Categories", "acs5",
                             "group(B02001)"),                         # 10 vars
    "WHITE_ALONE":          ("Pop_White_Alone", "acs5",
                             ("B02001_002E",)),
    "BLACK_ALONE":          ("Pop_Black_Alone", "acs5",
                             ("B02001_003E",)),
    "AIAN_ALONE":           ("Pop_American_Indian_Alaska_Native", "acs5",
                             ("B02001_004E",)),
    "ASIAN_ALONE":          ("Pop_Asian_Alone", "acs5",
                             ("B02001_005E",)),
    "NHPI_ALONE":           ("Pop_Native_Hawaiian_Pacific_Islander", "acs5",
                             ("B02001_006E",)),
    "OTHER_ALONE":          ("Pop_Other_Race_Alone", "acs5",
                             ("B02001_007E",)),
    "TWO_OR_MORE":          ("Pop_Two_Or_More_Races", "acs5",
                             ("B02001_008E",)),
    "ASIAN_DETAIL":         ("Asian_Subgroups_Detail", "acs5",
                             "group(B02015)"),                         # Chinese, Indian, Filipino, etc.
}

HISPANIC_ORIGIN = {
    "HISPANIC_TOTAL":       ("Hispanic_Or_Latino_Origin", "acs5",
                             "group(B03003)"),                         # Hispanic yes/no
    "HISPANIC_BY_RACE":     ("Hispanic_By_Race", "acs5",
                             "group(B03002)"),                         # 21 vars: Hispanic × race
    "HISPANIC_ORIGIN_DETAIL":("Hispanic_Origin_Detail", "acs5",
                             "group(B03001)"),                         # Mexican, Puerto Rican, Cuban…
    "WHITE_NOT_HISPANIC":   ("Pop_White_Alone_Not_Hispanic", "acs5",
                             ("B03002_003E",)),
}

RACE_ETHNICITY = {**RACE, **HISPANIC_ORIGIN}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  NATIVITY, CITIZENSHIP & MIGRATION                                      ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

NATIVITY = {
    "NATIVE_FOREIGN_BORN":  ("Nativity_Native_vs_Foreign", "acs5",
                             "group(B05002)"),                         # native, foreign born, naturalized
    "FOREIGN_BORN_TOTAL":   ("Foreign_Born_Total", "acs5",
                             ("B05002_013E",)),
    "CITIZENSHIP_STATUS":   ("Citizenship_Status", "acs5",
                             "group(B05001)"),                         # citizen, not citizen, etc.
    "NOT_US_CITIZEN":       ("Pop_Not_US_Citizen", "acs5",
                             ("B05001_006E",)),
    "PLACE_OF_BIRTH":       ("Place_Of_Birth_Foreign", "acs5",
                             "group(B05006)"),                         # by world region / country
    "YEAR_OF_ENTRY":        ("Year_Of_Entry_Foreign_Born", "acs5",
                             "group(B05005)"),
}

MIGRATION = {
    "GEO_MOBILITY_1YR":     ("Geographic_Mobility_Past_Year", "acs5",
                             "group(B07001)"),                         # same house, moved within, etc.
    "MOVERS_SAME_COUNTY":   ("Moved_Within_Same_County", "acs5",
                             ("B07001_033E",)),
    "MOVERS_DIFF_STATE":    ("Moved_From_Different_State", "acs5",
                             ("B07001_065E",)),
    "MOVERS_FROM_ABROAD":   ("Moved_From_Abroad", "acs5",
                             ("B07001_081E",)),
    "MIGRATION_FLOWS":      ("County_To_County_Migration_Flows", "acs5/flows",
                             ("MOVEDIN", "MOVEDOUT", "MOVEDNET")),     # separate dataset
}

NATIVITY_MIGRATION = {**NATIVITY, **MIGRATION}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  LANGUAGE                                                               ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

LANGUAGE = {
    "LANGUAGE_AT_HOME":     ("Language_Spoken_At_Home", "acs5",
                             "group(B16001)"),                         # 119 vars: each language × English ability
    "ENGLISH_ABILITY":      ("English_Speaking_Ability", "acs5",
                             "group(B06007)"),
    "SPEAK_ONLY_ENGLISH":   ("Speak_Only_English", "acs5",
                             ("B16001_002E",)),
    "SPEAK_SPANISH":        ("Speak_Spanish_At_Home", "acs5",
                             ("B16001_003E",)),
    "LIMITED_ENGLISH_HH":   ("Limited_English_Households", "acs5",
                             "group(B16002)"),                         # linguistically isolated HH
    "LANGUAGE_PROFILE":     ("Language_Subject_Table", "acs5/subject",
                             "group(S1601)"),
}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  EDUCATION                                                              ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

SCHOOL_ENROLLMENT = {
    "ENROLLMENT_BY_LEVEL":  ("School_Enrollment_By_Level", "acs5",
                             "group(B14001)"),                         # nursery–grad school
    "ENROLLMENT_TYPE":      ("School_Enrollment_Public_Private", "acs5",
                             "group(B14002)"),
    "ENROLLMENT_PROFILE":   ("Enrollment_Subject_Table", "acs5/subject",
                             "group(S1401)"),
}

EDUCATIONAL_ATTAINMENT = {
    "ATTAINMENT_25PLUS":    ("Educational_Attainment_25Plus", "acs5",
                             "group(B15003)"),                         # 25 levels: no school … doctorate
    "BACHELORS_OR_HIGHER":  ("Pct_Bachelors_Or_Higher", "acs5",
                             ("B15003_022E", "B15003_023E",
                              "B15003_024E", "B15003_025E")),          # BA, MA, prof, doctorate
    "HS_GRAD_OR_HIGHER":    ("HS_Grad_Or_Higher_Count", "acs5",
                             ("B15003_017E", "B15003_018E", "B15003_019E",
                              "B15003_020E", "B15003_021E", "B15003_022E",
                              "B15003_023E", "B15003_024E", "B15003_025E")),
    "ATTAINMENT_BY_RACE":   ("Educational_Attainment_By_Race", "acs5",
                             "group(C15002)"),                         # collapsed, by race iterations
    "ATTAINMENT_BY_SEX":    ("Educational_Attainment_By_Sex", "acs5",
                             "group(B15002)"),
    "FIELD_OF_DEGREE":      ("Field_Of_Bachelors_Degree", "acs5",
                             "group(B15012)"),                         # STEM, business, arts, etc.
    "ATTAINMENT_PROFILE":   ("Attainment_Subject_Table", "acs5/subject",
                             "group(S1501)"),
}

EDUCATION = {**SCHOOL_ENROLLMENT, **EDUCATIONAL_ATTAINMENT}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  HOUSEHOLDS & FAMILIES                                                  ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

HOUSEHOLD_TYPE = {
    "HOUSEHOLD_TYPE":       ("Household_Type", "acs5",
                             "group(B11001)"),                         # family, nonfamily, living alone
    "TOTAL_HOUSEHOLDS":     ("Total_Households", "acs5",
                             ("B11001_001E",)),
    "FAMILY_HOUSEHOLDS":    ("Family_Households", "acs5",
                             ("B11001_002E",)),
    "MARRIED_COUPLE_HH":    ("Married_Couple_Family_HH", "acs5",
                             ("B11001_003E",)),
    "FEMALE_HOUSEHOLDER":   ("Female_Householder_No_Spouse", "acs5",
                             ("B11001_006E",)),
    "LIVING_ALONE":         ("Living_Alone", "acs5",
                             ("B11001_008E",)),
    "AVG_HOUSEHOLD_SIZE":   ("Average_Household_Size", "acs5",
                             ("B25010_001E",)),
    "AVG_FAMILY_SIZE":      ("Average_Family_Size", "acs5",
                             ("B25010_002E",)),
}

MARITAL_STATUS = {
    "MARITAL_STATUS_15PLUS": ("Marital_Status_15Plus", "acs5",
                             "group(B12001)"),                         # never, now, separated, widowed, divorced
    "MARITAL_BY_SEX_AGE":   ("Marital_By_Sex_And_Age", "acs5",
                             "group(B12002)"),
}

FERTILITY = {
    "FERTILITY_BY_AGE":     ("Women_15_50_Births_Past_Year", "acs5",
                             "group(B13002)"),
    "FERTILITY_RATE":       ("Fertility_Subject_Table", "acs5/subject",
                             "group(S1301)"),
}

HOUSEHOLDS = {**HOUSEHOLD_TYPE, **MARITAL_STATUS, **FERTILITY}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  INCOME & EARNINGS                                                      ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

HOUSEHOLD_INCOME = {
    "MEDIAN_HH_INCOME":    ("Median_Household_Income", "acs5",
                             ("B19013_001E",)),
    "MEAN_HH_INCOME":      ("Mean_Household_Income", "acs5",
                             ("B19025_001E",)),
    "HH_INCOME_BRACKETS":  ("Household_Income_Distribution", "acs5",
                             "group(B19001)"),                         # 17 income brackets
    "MEDIAN_INCOME_WHITE":  ("Median_HH_Income_White", "acs5",
                             ("B19013A_001E",)),
    "MEDIAN_INCOME_BLACK":  ("Median_HH_Income_Black", "acs5",
                             ("B19013B_001E",)),
    "MEDIAN_INCOME_HISPANIC":("Median_HH_Income_Hispanic", "acs5",
                             ("B19013I_001E",)),
    "MEDIAN_INCOME_ASIAN":  ("Median_HH_Income_Asian", "acs5",
                             ("B19013D_001E",)),
    "PER_CAPITA_INCOME":    ("Per_Capita_Income", "acs5",
                             ("B19301_001E",)),
    "AGGREGATE_INCOME":     ("Aggregate_Household_Income", "acs5",
                             ("B19025_001E",)),
}

EARNINGS = {
    "MEDIAN_EARNINGS":      ("Median_Earnings_Workers", "acs5",
                             ("B20002_001E",)),
    "EARNINGS_BY_SEX":      ("Earnings_By_Sex_Full_Time", "acs5",
                             "group(B20017)"),
    "EARNINGS_BY_EDUCATION":("Earnings_By_Educational_Attainment", "acs5",
                             "group(B20004)"),
    "EARNINGS_PROFILE":     ("Earnings_Subject_Table", "acs5/subject",
                             "group(S2001)"),
}

PUBLIC_ASSISTANCE = {
    "SNAP_HOUSEHOLDS":      ("Households_Receiving_SNAP", "acs5",
                             "group(B22001)"),                         # with/without SNAP
    "SNAP_BY_RACE":         ("SNAP_By_Race_Of_Householder", "acs5",
                             "group(B22005)"),
    "PUBLIC_ASSISTANCE_INC":("Households_Public_Assistance_Income", "acs5",
                             "group(B19057)"),
    "SSI_INCOME":           ("Households_With_SSI", "acs5",
                             "group(B19056)"),
    "SOCIAL_SECURITY":      ("Households_With_Social_Security", "acs5",
                             "group(B19055)"),
}

INCOME = {**HOUSEHOLD_INCOME, **EARNINGS, **PUBLIC_ASSISTANCE}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  POVERTY                                                                ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

ACS_POVERTY = {
    "POVERTY_STATUS":       ("Poverty_Status_All", "acs5",
                             "group(B17001)"),                         # by age × sex
    "POVERTY_RATE_ALL":     ("Poverty_Rate_Subject_Table", "acs5/subject",
                             "group(S1701)"),                         # pct below poverty
    "POVERTY_BY_RACE":      ("Poverty_By_Race", "acs5",
                             ("B17001A_002E", "B17001B_002E",          # White, Black
                              "B17001D_002E", "B17001I_002E")),        # Asian, Hispanic below poverty
    "POVERTY_CHILDREN":     ("Poverty_Children_Under_18", "acs5",
                             "group(B17006)"),
    "POVERTY_FAMILIES":     ("Poverty_Families_By_Type", "acs5",
                             "group(B17010)"),                         # married, female HH, etc.
    "POVERTY_BY_EDUCATION": ("Poverty_By_Educational_Attainment", "acs5",
                             "group(B17003)"),
    "RATIO_INCOME_POVERTY": ("Income_To_Poverty_Ratio", "acs5",
                             "group(C17002)"),                         # <0.5, 0.5–0.99, 1.0–1.24…
}

# SAIPE: model-based poverty for ALL counties & school districts (more
# precise than ACS at small areas).  Timeseries — use YEAR= predicate.
SAIPE_POVERTY = {
    "SAIPE_POVERTY_ALL":    ("SAIPE_All_Ages_In_Poverty", "saipe",
                             ("SAEPOVALL_PT", "SAEPOVRTALL_PT")),      # count, rate
    "SAIPE_POVERTY_0_17":   ("SAIPE_Children_0_17_In_Poverty", "saipe",
                             ("SAEPOV0_17_PT", "SAEPOVRT0_17_PT")),
    "SAIPE_POVERTY_5_17":   ("SAIPE_Children_5_17_In_Poverty", "saipe",
                             ("SAEPOV5_17RV_PT", "SAEPOVRT5_17RV_PT")),
    "SAIPE_MEDIAN_HH_INC":  ("SAIPE_Median_Household_Income", "saipe",
                             ("SAEMHI_PT",)),
    "SAIPE_SCHOOL_DISTRICT":("SAIPE_School_District_Poverty", "saipe/schdist",
                             ("SD_NAME", "SAEPOV5_17RV_PT")),
}

POVERTY = {**ACS_POVERTY, **SAIPE_POVERTY}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  HEALTH INSURANCE                                                       ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

ACS_HEALTH_INSURANCE = {
    "HEALTH_INS_COVERAGE":  ("Health_Insurance_Coverage_Type", "acs5",
                             "group(B27010)"),                         # by age × coverage type
    "UNINSURED_TOTAL":      ("Pop_Without_Health_Insurance", "acs5",
                             ("B27010_017E", "B27010_033E",
                              "B27010_050E", "B27010_066E")),          # uninsured by age group
    "HEALTH_INS_BY_RACE":   ("Health_Insurance_By_Race", "acs5/subject",
                             "group(S2701)"),
    "HEALTH_INS_PROFILE":   ("Health_Insurance_Data_Profile", "acs5/profile",
                             ("DP03_0096E", "DP03_0096PE",             # with coverage, pct
                              "DP03_0099E", "DP03_0099PE")),           # no coverage, pct
}

# SAHIE: model-based health insurance for ALL counties.
# Timeseries — filterable by AGECAT, RACECAT, SEXCAT, IPRCAT.
SAHIE_HEALTH_INSURANCE = {
    "SAHIE_INSURED_RATE":   ("SAHIE_Pct_Insured", "sahie",
                             ("NIC_PT", "PCTIC_PT")),                  # count insured, pct insured
    "SAHIE_UNINSURED_RATE": ("SAHIE_Pct_Uninsured", "sahie",
                             ("NUI_PT", "PCTUI_PT")),                  # count uninsured, pct uninsured
}

HEALTH_INSURANCE = {**ACS_HEALTH_INSURANCE, **SAHIE_HEALTH_INSURANCE}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  EMPLOYMENT & COMMUTING                                                 ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

EMPLOYMENT_STATUS = {
    "EMPLOYMENT_STATUS":    ("Employment_Status_16Plus", "acs5",
                             "group(B23025)"),                         # in labor force, employed, unemployed
    "UNEMPLOYMENT_RATE":    ("Employment_Status_Subject", "acs5/subject",
                             "group(S2301)"),                          # has % unemployed
    "LABOR_FORCE_PART":     ("Labor_Force_Participation", "acs5",
                             ("B23025_002E", "B23025_001E")),          # in LF / total 16+
    "EMPLOYMENT_BY_SEX":    ("Employment_By_Sex", "acs5",
                             "group(B23001)"),                         # sex × age × in LF
}

OCCUPATION_INDUSTRY = {
    "OCCUPATION":           ("Occupation_Of_Workers", "acs5",
                             "group(C24010)"),                         # management, service, sales…
    "INDUSTRY":             ("Industry_Of_Workers", "acs5",
                             "group(C24030)"),                         # agriculture, construction, mfg…
    "CLASS_OF_WORKER":      ("Class_Of_Worker", "acs5",
                             "group(B24080)"),                         # private, govt, self-employed
    "SELF_EMPLOYED":        ("Self_Employment", "acs5",
                             ("B24080_005E", "B24080_006E",            # self-employed incorp / not
                              "B24080_012E", "B24080_013E")),
    "WORK_STATUS":          ("Work_Status_Past_Year", "acs5",
                             "group(B23027)"),                         # full-time, part-time, didn't work
}

COMMUTING = {
    "COMMUTE_MODE":         ("Means_Of_Transportation_To_Work", "acs5",
                             "group(B08301)"),                         # drove alone, carpool, transit, WFH…
    "WORK_FROM_HOME":       ("Worked_From_Home", "acs5",
                             ("B08301_021E",)),
    "COMMUTE_TIME":         ("Travel_Time_To_Work", "acs5",
                             "group(B08303)"),                         # <10 min, 10-14, …, 90+
    "MEDIAN_COMMUTE_TIME":  ("Median_Commute_Minutes", "acs5",
                             ("B08136_001E",)),                        # aggregate, divide by workers
    "COMMUTE_PROFILE":      ("Commuting_Subject_Table", "acs5/subject",
                             "group(S0801)"),
    "PLACE_OF_WORK":        ("Place_Of_Work_State_County", "acs5",
                             "group(B08007)"),                         # work in state, out of state
}

EMPLOYMENT = {**EMPLOYMENT_STATUS, **OCCUPATION_INDUSTRY, **COMMUTING}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  HOUSING CHARACTERISTICS                                                ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

HOUSING_UNITS = {
    "TOTAL_HOUSING_UNITS":  ("Total_Housing_Units", "acs5",
                             ("B25001_001E",)),
    "OCCUPANCY_STATUS":     ("Occupancy_Vacant_Occupied", "acs5",
                             "group(B25002)"),
    "VACANCY_STATUS":       ("Vacancy_Status_Detail", "acs5",
                             "group(B25004)"),                         # for rent, rented, for sale, etc.
    "UNITS_IN_STRUCTURE":   ("Units_In_Structure", "acs5",
                             "group(B25024)"),                         # 1-detached, 2, 3-4, 5-9, 10-19, 20+, mobile
    "YEAR_BUILT":           ("Year_Structure_Built", "acs5",
                             "group(B25034)"),                         # 2020+, 2010-19, 2000-09, …
    "ROOMS":                ("Number_Of_Rooms", "acs5",
                             "group(B25017)"),
    "BEDROOMS":             ("Number_Of_Bedrooms", "acs5",
                             "group(B25041)"),
}

TENURE = {
    "TENURE_OWN_RENT":      ("Tenure_Owner_Renter", "acs5",
                             "group(B25003)"),                         # owner-occupied, renter-occupied
    "HOMEOWNERSHIP_RATE":   ("Homeownership_Rate", "acs5",
                             ("B25003_002E", "B25003_001E")),          # owners / occupied HU
    "TENURE_BY_RACE":       ("Tenure_By_Race", "acs5",
                             ("B25003A_002E", "B25003A_003E",          # White own/rent
                              "B25003B_002E", "B25003B_003E",          # Black own/rent
                              "B25003D_002E", "B25003D_003E",          # Asian own/rent
                              "B25003I_002E", "B25003I_003E")),        # Hispanic own/rent
    "TENURE_BY_AGE":        ("Tenure_By_Age_Of_Householder", "acs5",
                             "group(B25007)"),
}

HOME_VALUE = {
    "MEDIAN_HOME_VALUE":    ("Median_Home_Value_Owner_Occ", "acs5",
                             ("B25077_001E",)),
    "HOME_VALUE_DIST":      ("Home_Value_Distribution", "acs5",
                             "group(B25075)"),                         # <$10k, $10k-14.9k, …, $2M+
    "MEDIAN_RENT":          ("Median_Gross_Rent", "acs5",
                             ("B25064_001E",)),
    "RENT_DISTRIBUTION":    ("Gross_Rent_Distribution", "acs5",
                             "group(B25063)"),
    "RENT_BURDEN":          ("Gross_Rent_As_Pct_Income", "acs5",
                             "group(B25070)"),                         # <10%, 10-14.9%, …, 50%+
    "OWNER_COST_BURDEN":    ("Owner_Costs_As_Pct_Income_Mortgage", "acs5",
                             "group(B25091)"),                         # <10%, 10-14.9%, …, 50%+
    "MORTGAGE_STATUS":      ("Mortgage_Status", "acs5",
                             "group(B25081)"),                         # with/without mortgage
}

HOUSING_INFRASTRUCTURE = {
    "PLUMBING":             ("Plumbing_Facilities", "acs5",
                             "group(B25047)"),
    "KITCHEN":              ("Kitchen_Facilities", "acs5",
                             "group(B25051)"),
    "HEATING_FUEL":         ("House_Heating_Fuel", "acs5",
                             "group(B25040)"),                         # gas, electric, oil, wood, solar, none
    "VEHICLES_AVAILABLE":   ("Vehicles_Available", "acs5",
                             "group(B25044)"),                         # 0, 1, 2, 3+
    "NO_VEHICLE":           ("Households_No_Vehicle", "acs5",
                             ("B25044_003E", "B25044_010E")),          # owner 0 + renter 0
    "INTERNET_ACCESS":      ("Internet_Access_Type", "acs5/subject",
                             "group(S2801)"),                          # broadband, cellular, none
    "COMPUTER_IN_HH":       ("Computer_And_Internet_In_HH", "acs5",
                             "group(B28001)"),                         # has computer, no computer
}

HOUSING = {**HOUSING_UNITS, **TENURE, **HOME_VALUE, **HOUSING_INFRASTRUCTURE}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  DISABILITY                                                             ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

DISABILITY = {
    "DISABILITY_STATUS":    ("Disability_Status_By_Age", "acs5",
                             "group(B18101)"),                         # with/without by age
    "DISABILITY_TYPE":      ("Disability_Type_By_Age", "acs5",
                             "group(B18102)"),                         # hearing, vision, cognitive, ambulatory…
    "DISABILITY_BY_SEX":    ("Disability_By_Sex", "acs5/subject",
                             "group(S1810)"),
    "DISABILITY_EMPLOYMENT":("Disability_Employment_Status", "acs5",
                             "group(B18120)"),                         # employed, unemployed, not in LF
    "DISABILITY_PROFILE":   ("Disability_Data_Profile", "acs5/profile",
                             ("DP02_0072E", "DP02_0072PE")),           # civilian with disability, pct
}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  VETERANS                                                               ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

VETERANS = {
    "VETERAN_STATUS":       ("Veteran_Status_18Plus", "acs5",
                             "group(B21001)"),                         # veteran, nonveteran × sex
    "VETERAN_PERIOD":       ("Veteran_By_Period_Of_Service", "acs5",
                             "group(B21002)"),                         # Gulf War, Vietnam, Korea, WWII…
    "VETERAN_DISABILITY":   ("Veteran_Disability_Status", "acs5",
                             "group(B21100)"),                         # with/without service-connected
    "VETERAN_PROFILE":      ("Veteran_Subject_Table", "acs5/subject",
                             "group(S2101)"),
}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  POPULATION ESTIMATES PROGRAM  (PEP)                                    ║
# ╚═══════════════════════════════════════════════════════════════════════════╝
#
# Annual intercensal estimates.  Dataset = pep/charv (2020-base vintage).
# Filterable by AGE, SEX, RACE, HISP, POPGROUP predicates.
# Available for nation, states, counties.

PEP_POPULATION = {
    "PEP_TOTAL":            ("PEP_Total_Population", "pep",
                             ("POP",)),
    "PEP_BY_AGE_SEX":       ("PEP_By_Age_Sex", "pep",
                             ("POP", "AGE", "SEX")),
    "PEP_BY_RACE_HISP":     ("PEP_By_Race_Hispanic", "pep",
                             ("POP", "RACE", "HISP")),
    "PEP_BY_POPGROUP":      ("PEP_By_Population_Group", "pep",
                             ("POP", "POPGROUP")),
    "PEP_COMPONENTS":       ("PEP_Components_Of_Change", "pep",
                             ("BIRTHS", "DEATHS", "NATURALINC",
                              "INTERNATIONALMIG", "DOMESTICMIG",
                              "NETMIG", "NPOPCHG")),
    "PEP_HOUSING_UNITS":    ("PEP_Housing_Units", "pep",
                             ("HUEST",)),
}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  DECENNIAL CENSUS                                                       ║
# ╚═══════════════════════════════════════════════════════════════════════════╝
#
# 2020 Decennial — two main files:
#   dec/pl   = P.L. 94-171 Redistricting Data (race/ethnicity + voting age)
#   dec/dhc  = Demographic & Housing Characteristics
# Available down to BLOCK level.

DECENNIAL_REDISTRICTING = {
    "DEC_TOTAL_POP":        ("Dec2020_Total_Pop", "dec/pl",
                             ("P1_001N",)),                            # total pop
    "DEC_RACE":             ("Dec2020_Race", "dec/pl",
                             ("P1_003N", "P1_004N", "P1_005N",         # White, Black, AIAN
                              "P1_006N", "P1_007N", "P1_008N",         # Asian, NHPI, Other
                              "P1_009N")),                             # Two+
    "DEC_HISPANIC":         ("Dec2020_Hispanic_Origin", "dec/pl",
                             ("P2_002N", "P2_003N")),                  # Hispanic, Not Hispanic
    "DEC_VOTING_AGE":       ("Dec2020_Voting_Age_18Plus", "dec/pl",
                             ("P3_001N",)),
    "DEC_HOUSING_OCC":      ("Dec2020_Housing_Occupancy", "dec/pl",
                             ("H1_001N", "H1_002N", "H1_003N")),       # total, occupied, vacant
}

DECENNIAL_DHC = {
    "DEC_AGE_SEX":          ("Dec2020_Age_By_Sex", "dec/dhc",
                             "group(P12)"),                            # single-year-of-age × sex
    "DEC_HOUSEHOLD_TYPE":   ("Dec2020_Household_Type", "dec/dhc",
                             "group(P20)"),
    "DEC_GROUP_QUARTERS":   ("Dec2020_Group_Quarters", "dec/dhc",
                             "group(P42)"),                            # institutional, noninstitutional
    "DEC_TENURE":           ("Dec2020_Tenure", "dec/dhc",
                             "group(H4)"),                             # owner, renter
}

DECENNIAL = {**DECENNIAL_REDISTRICTING, **DECENNIAL_DHC}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  DATA PROFILES  (broad summary tables)                                  ║
# ╚═══════════════════════════════════════════════════════════════════════════╝
#
# Each DP table is a one-stop shop for a broad topic.  Good for dashboards.

DATA_PROFILES = {
    "DP_SOCIAL":            ("Profile_Social_Characteristics", "acs5/profile",
                             "group(DP02)"),                           # education, marital, ancestry, language…
    "DP_ECONOMIC":          ("Profile_Economic_Characteristics", "acs5/profile",
                             "group(DP03)"),                           # employment, income, industry, health ins…
    "DP_HOUSING":           ("Profile_Housing_Characteristics", "acs5/profile",
                             "group(DP04)"),                           # tenure, value, rent, structure, heating…
    "DP_DEMOGRAPHIC":       ("Profile_Demographic_Characteristics", "acs5/profile",
                             "group(DP05)"),                           # sex, age, race, Hispanic origin
}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  PREDICATE FILTERS                                                      ║
# ╚═══════════════════════════════════════════════════════════════════════════╝
#
# For datasets that use categorical predicates (PEP, SAHIE, etc.), store
# the valid values here so the loader can loop or filter.

PREDICATES = {
    # ── PEP race codes ────────────────────────────────────────────────────
    "PEP_RACE": {
        0: "All_Races",
        1: "White_Alone",
        2: "Black_Alone",
        3: "American_Indian_Alaska_Native_Alone",
        4: "Asian_Alone",
        5: "Native_Hawaiian_Pacific_Islander_Alone",
        6: "Two_Or_More_Races",
    },
    # ── PEP Hispanic origin ──────────────────────────────────────────────
    "PEP_HISP": {
        0: "Total",
        1: "Not_Hispanic",
        2: "Hispanic",
    },
    # ── PEP sex ───────────────────────────────────────────────────────────
    "PEP_SEX": {
        0: "Both_Sexes",
        1: "Male",
        2: "Female",
    },
    # ── SAHIE age category ────────────────────────────────────────────────
    "SAHIE_AGECAT": {
        0: "Under_65",
        1: "18_to_64",
        2: "40_to_64",
        3: "50_to_64",
        4: "Under_19",
        5: "21_to_64",
    },
    # ── SAHIE income-to-poverty ratio ─────────────────────────────────────
    "SAHIE_IPRCAT": {
        0: "All_Incomes",
        1: "At_Or_Below_200pct_FPL",
        2: "At_Or_Below_250pct_FPL",
        3: "At_Or_Below_138pct_FPL",
        4: "At_Or_Below_400pct_FPL",
        5: "Between_138_and_400pct_FPL",
    },
    # ── SAHIE race/ethnicity ──────────────────────────────────────────────
    "SAHIE_RACECAT": {
        0: "All_Races",
        1: "White_Alone_Not_Hispanic",
        2: "Black_Alone",
        3: "Hispanic_Any_Race",
    },
    # ── SAHIE sex ─────────────────────────────────────────────────────────
    "SAHIE_SEXCAT": {
        0: "Both_Sexes",
        1: "Male",
        2: "Female",
    },
}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  COMPOSITES                                                             ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

ALL_SERIES = {
    **POPULATION,
    **RACE_ETHNICITY,
    **NATIVITY_MIGRATION,
    **LANGUAGE,
    **EDUCATION,
    **HOUSEHOLDS,
    **INCOME,
    **POVERTY,
    **HEALTH_INSURANCE,
    **EMPLOYMENT,
    **HOUSING,
    **DISABILITY,
    **VETERANS,
    **PEP_POPULATION,
    **DECENNIAL,
    **DATA_PROFILES,
}

# ── Category lookup (top-level) ───────────────────────────────────────────
CATEGORIES = {
    "POPULATION":        POPULATION,
    "RACE_ETHNICITY":    RACE_ETHNICITY,
    "NATIVITY_MIGRATION":NATIVITY_MIGRATION,
    "LANGUAGE":          LANGUAGE,
    "EDUCATION":         EDUCATION,
    "HOUSEHOLDS":        HOUSEHOLDS,
    "INCOME":            INCOME,
    "POVERTY":           POVERTY,
    "HEALTH_INSURANCE":  HEALTH_INSURANCE,
    "EMPLOYMENT":        EMPLOYMENT,
    "HOUSING":           HOUSING,
    "DISABILITY":        DISABILITY,
    "VETERANS":          VETERANS,
    "PEP_POPULATION":    PEP_POPULATION,
    "DECENNIAL":         DECENNIAL,
    "DATA_PROFILES":     DATA_PROFILES,
}

# ── Subcategory lookup (nested, with variable references) ─────────────────
SUBCATEGORIES = {
    "POPULATION": {
        "TOTAL_POPULATION": TOTAL_POPULATION,
        "AGE_DETAIL":       AGE_DETAIL,
    },
    "RACE_ETHNICITY": {
        "RACE":             RACE,
        "HISPANIC_ORIGIN":  HISPANIC_ORIGIN,
    },
    "NATIVITY_MIGRATION": {
        "NATIVITY":         NATIVITY,
        "MIGRATION":        MIGRATION,
    },
    "LANGUAGE": {},
    "EDUCATION": {
        "SCHOOL_ENROLLMENT":     SCHOOL_ENROLLMENT,
        "EDUCATIONAL_ATTAINMENT":EDUCATIONAL_ATTAINMENT,
    },
    "HOUSEHOLDS": {
        "HOUSEHOLD_TYPE":   HOUSEHOLD_TYPE,
        "MARITAL_STATUS":   MARITAL_STATUS,
        "FERTILITY":        FERTILITY,
    },
    "INCOME": {
        "HOUSEHOLD_INCOME": HOUSEHOLD_INCOME,
        "EARNINGS":         EARNINGS,
        "PUBLIC_ASSISTANCE": PUBLIC_ASSISTANCE,
    },
    "POVERTY": {
        "ACS_POVERTY":      ACS_POVERTY,
        "SAIPE_POVERTY":    SAIPE_POVERTY,
    },
    "HEALTH_INSURANCE": {
        "ACS_HEALTH_INSURANCE":  ACS_HEALTH_INSURANCE,
        "SAHIE_HEALTH_INSURANCE":SAHIE_HEALTH_INSURANCE,
    },
    "EMPLOYMENT": {
        "EMPLOYMENT_STATUS":     EMPLOYMENT_STATUS,
        "OCCUPATION_INDUSTRY":   OCCUPATION_INDUSTRY,
        "COMMUTING":             COMMUTING,
    },
    "HOUSING": {
        "HOUSING_UNITS":         HOUSING_UNITS,
        "TENURE":                TENURE,
        "HOME_VALUE":            HOME_VALUE,
        "HOUSING_INFRASTRUCTURE":HOUSING_INFRASTRUCTURE,
    },
    "DISABILITY": {},
    "VETERANS": {},
    "PEP_POPULATION": {},
    "DECENNIAL": {
        "DECENNIAL_REDISTRICTING": DECENNIAL_REDISTRICTING,
        "DECENNIAL_DHC":           DECENNIAL_DHC,
    },
    "DATA_PROFILES": {},
}
