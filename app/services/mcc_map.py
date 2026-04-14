from __future__ import annotations

MCC_TO_CATEGORY: dict[str, str] = {
    "eating places and restaurants": "dining",
    "quick payment service-fast food restaurants": "fast food",
    "miscellaneous food stores-convenience stores and specialty markets": "convenience store",
    "grocery stores and supermarkets": "groceries",
    "wholesale club with or without membership fee": "wholesale / costco",
    "taxicabs and limousines": "transportation",
    "cable satellite and other pay television and radio services": "cable / internet",
    "telecommunication services including local and long distance calls credit card calls"
    " call through use of magnetic-strip-reading telephones and fax services": "phone",
    "utilities-electric gas water and sanitary": "utilities",
    "business services": "business services",
    "computer network/information services and other online services such as electronic"
    " bulletin board e-mail web site hosting services or internet access": "online shopping",
    "computer software stores": "software",
    "digital goods \u2013 games": "gaming",
    "digital goods \u2013 media books movies music": "media / streaming",
    "large digital goods merchant": "digital goods",
    "continuity/subscription merchants": "subscriptions",
    "colleges universities professional schools and junior colleges": "education",
    "continuity/subscription": "subscriptions",
}

PAYMENT_KEYWORDS = ["payment thank you", "payment - thank you", "remboursement"]
CASHBACK_KEYWORDS = ["cash back", "cash back / remises", "rebate"]

# Default categories seeded on first run.
# Each entry: (name, hex_color, comma-separated merchant keyword patterns)
# Keywords are matched case-insensitively as substrings of the merchant name.
DEFAULT_CATEGORIES: list[tuple[str, str, str]] = [
    ("dining",           "#f59e0b", "restaurant,sushi,pizza,burger,cafe,coffee,bistro,grill,kitchen,eatery,diner,bake,bakery,brew,pub,bar,tavern,lounge,chili,hot pot,ramen,pho,thai,korean,chinese,italian,mexican,taco,sandwich,deli,food"),
    ("fast food",        "#ef4444", "mcdonald,tim horton,subway,wendy,burger king,kfc,popeyes,a&w,dairy queen,five guys,chipotle,domino,pizza hut,little caesar,harvey,starbucks,second cup,booster juice"),
    ("groceries",        "#10b981", "walmart,superstore,safeway,sobeys,loblaws,metro,iga,food basics,freshco,whole foods,t&t,h mart,costco,no frills,save-on,thrifty"),
    ("transportation",   "#3b82f6", "uber,lyft,taxi,transit,go train,via rail,parking,esso,petro,shell,canadian tire,gas,fuel,presto"),
    ("shopping",         "#8b5cf6", "amazon,amzn,ebay,etsy,best buy,the bay,winners,marshalls,old navy,gap,h&m,zara,uniqlo,sport chek,atmosphere,indigo,chapters"),
    ("subscriptions",    "#ec4899", "netflix,spotify,apple,google,microsoft,adobe,dropbox,youtube,hulu,disney,prime,linkedin,cursor,github,openai,chatgpt,claude,patreon"),
    ("phone",            "#06b6d4", "fido,rogers,bell,telus,koodo,public mobile,freedom,virgin,chatr,lucky mobile"),
    ("utilities",        "#14b8a6", "epcor,enmax,hydro,atco,fortis,union gas,alectra,toronto hydro,bc hydro,nova scotia power,nb power"),
    ("cable / internet", "#0ea5e9", "shaw,rogers,bell,telus,videotron,cogeco,eastlink,teksavvy,distributel"),
    ("health",           "#22c55e", "pharmacy,shoppers,rexall,london drugs,lawtons,pharmasave,guardian,clinic,dental,optom,vision,physio,chiro,massage,medical,health"),
    ("entertainment",    "#a855f7", "cineplex,landmark,imax,steam,playstation,xbox,nintendo,ticketmaster,eventbrite,live nation,sport,arena,stadium,museum,gallery,theatre,theater,concert,board game,escape room,mini golf,bowling,laser tag,arcade"),
    ("travel",           "#f97316", "airbnb,hotel,motel,inn,marriott,hilton,hyatt,expedia,booking,kayak,air canada,westjet,porter,delta,united,american airlines,airport"),
    ("education",        "#84cc16", "university,college,udemy,coursera,skillshare,duolingo,kwiziq,tutor,school,textbook"),
    ("software",         "#6366f1", "cursor,github,jetbrains,figma,notion,slack,zoom,atlassian,heroku,digitalocean,aws,azure,gcp,vercel,netlify"),
    ("gaming",           "#e11d48", "steam,epic games,playstation,xbox,nintendo,twitch,humble,gog,battlenet,riot"),
    ("media / streaming","#d946ef", "spotify,netflix,apple music,youtube,audible,kindle,kobo,crave,tubi,paramount,peacock"),
    ("transfers",        "#64748b", "e-transfer,interac,wire transfer,direct deposit,payroll,zelle,paypal,wise,revolut"),
    ("uncategorized",    "#475569", ""),
]


def mcc_to_category(mcc_description: str) -> str:
    if not mcc_description:
        return "uncategorized"
    key = mcc_description.strip().lower()
    return MCC_TO_CATEGORY.get(key, key)


def match_by_keywords(merchant_name: str, keyword_map: dict[str, list[str]]) -> str | None:
    name_lower = merchant_name.strip().lower()
    for cat_name, keywords in keyword_map.items():
        for kw in keywords:
            if kw and kw in name_lower:
                return cat_name
    return None


def is_payment(merchant_name: str, mcc_description: str) -> bool:
    combined = f"{merchant_name} {mcc_description}".lower()
    return any(kw in combined for kw in PAYMENT_KEYWORDS)


def is_cashback(merchant_name: str, mcc_description: str) -> bool:
    combined = f"{merchant_name} {mcc_description}".lower()
    return any(kw in combined for kw in CASHBACK_KEYWORDS)
