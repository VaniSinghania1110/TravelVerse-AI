"""
Smart Icebreakers & Chat Moderation Engine (TravelVerse)
Generates authentic, mixed conversation starters across:
1. Matching destination(s) with specific local landmarks and spots (rotated across all mutual destinations)
2. General travel compatibility & style questions (no destination forced)
3. Open bucket-list and upcoming trip discovery questions
4. Agent-side & Client-to-Agent professional travel operator inquiry modes
Includes real-time link/spam chat safety moderation.
"""

import os
import re
import math
import json
import random
import urllib.request
from typing import Dict, Any, List, Optional, Tuple

# -------------------------------------------------------------
# EXTENSIVE LANDMARK, CAFE & LOCAL SPOT KNOWLEDGE BASE
# -------------------------------------------------------------
DESTINATION_LANDMARKS: Dict[str, List[str]] = {
    # Goa
    "goa": [
        "Palolem Beach sunset shacks",
        "Anjuna flea market and beach cafes",
        "Chapora Fort sunset view",
        "Fontainhas heritage lanes in Panjim",
        "South Goa quiet beach shacks",
        "Arambol cliffside drum circle",
        "Vagator sunset cliffs",
        "Thalassa viewpoint",
        "Dudhsagar Falls day trek"
    ],
    # Manali
    "manali": [
        "Old Manali riverside cafes",
        "Jogini Waterfall hike",
        "Sethan Valley igloo village",
        "Mall Road bakeries and cafes",
        "Atal Tunnel drive up to Sissu",
        "Solang Valley viewpoints",
        "Vashisht village hot springs"
    ],
    # Kasol
    "kasol": [
        "Parvati Valley riverside cafes",
        "Chalal village trail",
        "Tosh village viewpoint cafes",
        "Kheerganga trek and hot springs",
        "German bakeries in Old Kasol",
        "Grahan village offbeat trek"
    ],
    # Rishikesh
    "rishikesh": [
        "Beatles Ashram graffiti ruins",
        "Triveni Ghat evening Ganga Aarti",
        "Little Buddha rooftop cafe",
        "Neer Garh waterfall trek",
        "white water rafting stretch at Shivpuri",
        "Laxman Jhula sunset viewpoints"
    ],
    # Ladakh / Leh
    "ladakh": [
        "Pangong Tso sunrise over the mountains",
        "Nubra Valley sand dunes",
        "Khardung La Pass summit",
        "Thiksey Monastery morning chants",
        "Tso Moriri quiet lake camps",
        "Leh Old Town apricot cafes"
    ],
    "leh": [
        "Pangong Tso sunrise",
        "Nubra Valley sand dunes",
        "Shanti Stupa sunset panorama",
        "Leh Old Market cafes",
        "Magnetic Hill drive"
    ],
    # Spiti
    "spiti": [
        "Key Monastery high on the cliffs",
        "Chandratal Lake mountain camp",
        "Hikkim highest post office",
        "Langza giant Buddha statue",
        "Kaza market cafes",
        "Chicham high suspension bridge"
    ],
    # Jaipur
    "jaipur": [
        "Nahargarh Fort sunset view over the city",
        "Hawa Mahal rooftop cafes",
        "Amer Fort courtyards",
        "Rawat Mishtan Bhandar kachori trail",
        "Bapu Bazaar shopping lanes",
        "Jal Mahal lake view"
    ],
    # Udaipur
    "udaipur": [
        "Lake Pichola sunset boat cruise",
        "Ambrai Ghat dinner by the water",
        "City Palace lakeside courtyards",
        "Fateh Sagar lake sunset promenade",
        "Badi Lake Bahubali peak trek"
    ],
    # Jodhpur
    "jodhpur": [
        "Mehrangarh Fort ramparts",
        "Blue City rooftop cafes",
        "Toorji Ka Jhalra stepwell",
        "Clock Tower Sardar Market"
    ],
    # Jaisalmer
    "jaisalmer": [
        "Sam sand dunes desert camp",
        "Golden Fort living alleys",
        "Gadisar Lake sunset boating",
        "Kuldhara abandoned heritage village"
    ],
    # Kerala / Munnar / Alleppey
    "kerala": [
        "Alleppey backwaters houseboat cruise",
        "Munnar tea garden trails",
        "Varkala cliffside sunset cafes",
        "Fort Kochi heritage street walk",
        "Marari quiet white beach"
    ],
    "munnar": [
        "Top Station panoramic viewpoint",
        "Kolukkumalai sunrise jeep trek",
        "Attukad waterfall trail",
        "Mattupetty dam and tea gardens"
    ],
    "alleppey": [
        "punnamada backwaters kayak trail",
        "Marari sunset beach",
        "heritage lighthouse",
        "local Toddy shop seafood trail"
    ],
    # Gokarna
    "gokarna": [
        "Kudle Beach sunset cafes",
        "Om Beach cliff hike",
        "Half Moon Beach hidden trail",
        "Paradise Beach remote camp",
        "Namaste Cafe overlooking the waves"
    ],
    # Pondicherry
    "pondicherry": [
        "White Town French quarter cafes",
        "Auroville Matrimandir peaceful gardens",
        "Promenade Beach night breeze",
        "Coromandel Cafe courtyard",
        "Serenity Beach surf point"
    ],
    # Hampi
    "hampi": [
        "Matanga Hill sunrise panorama",
        "Hippie Island boulder climbing",
        "Vittala Temple stone chariot",
        "Tungabhadra river coracle boat ride",
        "Mango Tree riverside cafe"
    ],
    # Meghalaya / Shillong
    "meghalaya": [
        "Cherrapunji double-decker root bridges",
        "Dawki crystal clear Umngot river boating",
        "Nohkalikai high waterfall view",
        "Dylan's Cafe in Shillong",
        "Krang Shuri turquoise waterfall"
    ],
    "shillong": [
        "Umiam Lake sunset waters",
        "Police Bazar street food lanes",
        "Laitlum Canyons foggy edge",
        "Dylan's Cafe live music nights"
    ],
    # Sikkim / Gangtok
    "sikkim": [
        "Gurudongmar high altitude lake",
        "MG Marg evening promenade",
        "Tsomgo Lake and mountain pass",
        "Ravangla Buddha Park",
        "Yumthang Valley flower trails"
    ],
    "gangtok": [
        "MG Marg local cafes and bakeries",
        "Ganesh Tok sunset viewpoint",
        "Rumtek Monastery",
        "Tashi Viewpoint mountain peaks"
    ],
    # Darjeeling
    "darjeeling": [
        "Tiger Hill sunrise over Kanchenjunga",
        "Glenary's bakery and heritage cafe",
        "Batasia Loop heritage toy train",
        "Happy Valley tea estate walks"
    ],
    # Shimla
    "shimla": [
        "Mall Road and the Ridge evening walk",
        "Jakhoo Temple pine forest trail",
        "Cafe Simla Times rooftop",
        "Mashobra peaceful nature trails"
    ],
    # Dharamshala / McLeodganj
    "dharamshala": [
        "Triund trek mountain ridge",
        "Bhagsunag waterfall cafes",
        "Namgyal Monastery peaceful halls",
        "Illiterati Books and Coffee cafe",
        "Dharamkot sunset view"
    ],
    "mcleodganj": [
        "Triund trek ridge",
        "Bhagsunag waterfall cafes",
        "Illiterati Books & Coffee",
        "Tibet Kitchen momo trail",
        "Dharamkot yoga cafes"
    ],
    # Mumbai
    "mumbai": [
        "Marine Drive Queen's Necklace sunset",
        "Bandra heritage cafes and Carter Road",
        "Colaba Causeway street shopping",
        "Prithvi Theatre cafe evening tea",
        "Gateway of India sea breeze",
        "Juhu Beach pav bhaji stalls"
    ],
    # Delhi
    "delhi": [
        "Hauz Khas Village lakeside rooftop cafes",
        "Old Delhi Chandni Chowk food walk",
        "Majnu Ka Tilla Tibetan cafes",
        "Lodhi Art District colorful murals",
        "Connaught Place inner circle cafes"
    ],
    # Bangalore
    "bangalore": [
        "Indiranagar specialty coffee roasters",
        "Cubbon Park morning shade walks",
        "Church Street bookstores and cafes",
        "Koramangala rooftop eateries",
        "VV Puram midnight food street"
    ],
    # Ahmedabad
    "ahmedabad": [
        "Sabarmati Riverfront promenade",
        "Manek Chowk midnight food market",
        "Old City heritage pol architecture",
        "Law Garden Khau Gali",
        "Kankaria Lake evening breeze"
    ],
    # Surat
    "surat": [
        "Dumas Beach sunset promenade",
        "Gopipura authentic locho street food trail",
        "Surat Castle heritage courtyards",
        "Dumas Road open-air cafes",
        "Tapi Riverfront walkway"
    ],
    # Udaipur
    "udaipur": [
        "Lake Pichola sunset boat ride",
        "Ambrai Ghat lakefront viewpoint",
        "City Palace heritage courtyards",
        "rooftop cafes overlooking Lake Pichola",
        "Sajjangarh Monsoon Palace sunset",
        "Bagore Ki Haveli evening cultural show",
        "Fateh Sagar Lake promenade"
    ],
    # Jaipur
    "jaipur": [
        "Hawa Mahal rooftop cafes",
        "Amer Fort heritage walk",
        "Nahargarh Fort sunset view",
        "Johari Bazaar authentic street food",
        "Patrika Gate colorful arches",
        "City Palace courtyards"
    ],
    # Varanasi
    "varanasi": [
        "Dashashwamedh Ghat evening Ganga Aarti",
        "Assi Ghat sunrise boat ride",
        "Blue Lassi shop in Vishwanath Gali",
        "Kashi heritage alleyways",
        "Manikarnika Ghat riverside"
    ],
    # Agra
    "agra": [
        "Taj Mahal sunrise from Mehtab Bagh",
        "Fatehpur Sikri sandstone courtyards",
        "Sadar Bazaar petha and chaat trail",
        "Agra Fort riverside towers"
    ],
    # Bali
    "bali": [
        "Ubud lush rice terraces and jungle swings",
        "Canggu beachfront sunset cafes",
        "Mount Batur early sunrise volcano trek",
        "Uluwatu cliffside temple and sunset view",
        "Nusa Penida Kelingking beach viewpoint",
        "Seminyak beach clubs and bistros"
    ],
    # Thailand / Bangkok / Phuket
    "thailand": [
        "Phi Phi islands crystal cruise",
        "Railay beach towering limestone cliffs",
        "Bangkok Yaowarat street food night crawl",
        "Chiang Mai old city temple cafes",
        "Chatuchak weekend market alleys"
    ],
    "bangkok": [
        "Yaowarat Chinatown night food crawl",
        "Chatuchak weekend market",
        "Wat Arun sunset across the river",
        "Khao San Road backpacker buzz",
        "rooftop sky bars overlooking the city"
    ],
    "phuket": [
        "Old Phuket Town colorful Sino-Portuguese streets",
        "Kata Noi quiet sunset beach",
        "Promthep Cape golden hour lookout",
        "Phi Phi island day boat tour"
    ],
    # Vietnam
    "vietnam": [
        "Ha Long Bay emerald water cruise",
        "Hoi An lantern-lit ancient river streets",
        "Hanoi Old Quarter egg coffee and street pho",
        "Sa Pa mountain terraced valley treks",
        "Da Nang Golden Bridge in the clouds"
    ],
    # Japan / Tokyo / Kyoto
    "japan": [
        "Shibuya crossing and Shinjuku izakaya alleys",
        "Kyoto Arashiyama bamboo grove",
        "Fushimi Inari thousand torii gate trail",
        "Akihabara neon streets",
        "Mount Fuji panoramic lake viewpoints"
    ],
    "tokyo": [
        "Shibuya scramble crossing",
        "Shinjuku Omoide Yokocho izakaya lanes",
        "Senso-ji temple in Asakusa",
        "Akihabara electronic and anime alleys",
        "Shimokitazawa vintage thrift cafes"
    ],
    # Dubai
    "dubai": [
        "Burj Khalifa observation deck at sunset",
        "desert dune bashing and Bedouin camp",
        "Dubai Marina illuminated walkway",
        "Old Deira gold and spice souks",
        "JBR beach promenade cafes"
    ],
    # Singapore
    "singapore": [
        "Gardens by the Bay Supertree light show",
        "Marina Bay Sands sky observation deck",
        "Haji Lane colorful graffiti cafes",
        "Chinatown Maxwell Food Centre hawker stalls",
        "Sentosa Island beach trails"
    ],
    # Paris
    "paris": [
        "Montmartre artistic cobblestone hills",
        "the Seine river golden hour cruise",
        "Saint-Germain historic cafe terraces",
        "Le Marais boutique and falafel quarter",
        "the Louvre illuminated courtyards at night"
    ],
    # Rome
    "rome": [
        "the Colosseum at dusk",
        "Trevi Fountain early morning before the crowds",
        "Trastevere authentic trattoria cobblestone alleys",
        "Piazza Navona street artists",
        "Spanish Steps evening view"
    ],
    # London
    "london": [
        "South Bank Thames river walk",
        "Borough Market gourmet street food stalls",
        "Camden Market alternative stalls and street food",
        "Covent Garden lively street performers",
        "Soho cafes and pub lanes"
    ],
    # Switzerland
    "switzerland": [
        "Interlaken paragliding over alpine lakes",
        "Jungfraujoch snowy Top of Europe",
        "Zermatt Matterhorn viewpoint trail",
        "Lauterbrunnen valley of 72 waterfalls",
        "Lake Geneva shoreline promenade"
    ],
    # Amsterdam
    "amsterdam": [
        "Jordaan canal bridges and vintage cafes",
        "De Pijp brunch cafes and Albert Cuyp market",
        "Vondelpark relaxed bike trails",
        "Rijksmuseum picturesque gardens"
    ],
    # Barcelona
    "barcelona": [
        "Park Güell mosaic terraces",
        "Gothic Quarter authentic tapas crawl",
        "Barceloneta beach golden hour promenade",
        "Bunkers del Carmel 360-degree sunset view"
    ]
}

# Generic local spot descriptors for destinations not in knowledge base
GENERIC_LOCAL_SPOTS = [
    "the local street food lanes",
    "hidden rooftop cafes with great views",
    "the most scenic sunset viewpoints",
    "the old town heritage streets",
    "offbeat local walking trails",
    "chill neighborhood cafes",
    "the local evening markets",
    "quiet lakeside or riverside spots",
    "scenic viewpoints away from tourist crowds"
]

GENERIC_DESTS = {
    "worldwide", "worldwide explorer", "explorer", "backpacker",
    "traveller", "traveler", "nomad", "globe", "anywhere", "none",
    "null", "undefined", "", "custom expeditions"
}

# -------------------------------------------------------------
# 1. PLACE & LOCAL QUESTIONS (Rotates destinations & landmarks)
# -------------------------------------------------------------
PLACE_STARTERS: List[Dict[str, str]] = [
    {
        "tag": "📍 Local Spots",
        "emoji": "📍",
        "text": "Hey {buddy_name}! Have you visited {landmark} in {destination} yet, or still planning your route?"
    },
    {
        "tag": "🗺️ Hidden Gems",
        "emoji": "🗺️",
        "text": "Thinking of checking out {landmark} while in {destination} — have you been there yet or down to explore together?"
    },
    {
        "tag": "🌅 Viewpoints",
        "emoji": "🌅",
        "text": "Any secret viewpoints or offbeat spots in {destination} that you've bookmarked so far?"
    },
    {
        "tag": "🍜 Foodie Trail",
        "emoji": "🍜",
        "text": "Know any great local food spots or hidden cafes around {destination}? Always hunting for good recommendations!"
    },
    {
        "tag": "🛵 Getting Around",
        "emoji": "🛵",
        "text": "What's your plan for getting around {destination}? Renting scooters, booking cabs, or using local transit?"
    },
    {
        "tag": "🏡 Stays & Hostels",
        "emoji": "🏡",
        "text": "Have you locked in a stay near {landmark} in {destination}, or still browsing hostels and homestays?"
    },
    {
        "tag": "🤝 Split & Save",
        "emoji": "🤝",
        "text": "Hey {buddy_name}! If our dates in {destination} align, totally down to split cabs or day excursions to keep things friendly!"
    },
    {
        "tag": "⏰ Early Bird",
        "emoji": "⏰",
        "text": "Are you planning to hit {landmark} early to beat the crowds, or keeping your days in {destination} relaxed?"
    },
    {
        "tag": "🍕 Street Food",
        "emoji": "🍕",
        "text": "Crucial trip question for {destination}: authentic local street food joints or aesthetic rooftop cafes?"
    },
    {
        "tag": "🗓️ Travel Dates",
        "emoji": "🗓️",
        "text": "Hey {buddy_name}! When are you planning to be in {destination}? Trying to see if our travel windows line up!"
    },
    {
        "tag": "🌄 Sunrise Vibe",
        "emoji": "🌄",
        "text": "Quick vibe check for {destination}: sunrise at {landmark} or sleeping in and starting relaxed? 🌄"
    },
    {
        "tag": "🚗 Shared Rides",
        "emoji": "🚗",
        "text": "Down to team up and share a ride or rental to check out {landmark} if you're heading that way?"
    },
    {
        "tag": "💡 Local Tips",
        "emoji": "💡",
        "text": "Hey {buddy_name}! Have you been to {destination} before, or is this your first time visiting?"
    },
    {
        "tag": "🥤 View Cafes",
        "emoji": "🥤",
        "text": "Any cafes with killer views around {destination} you're planning to work from or chill at?"
    },
    {
        "tag": "📸 Photo Spots",
        "emoji": "📸",
        "text": "Bringing a camera to shoot around {landmark}, or keeping it low-key with phone snaps?"
    }
]

# -------------------------------------------------------------
# 2. GENERAL TRAVEL STYLE & VIBE (NO DESTINATION FORCED)
# -------------------------------------------------------------
STYLE_STARTERS: List[Dict[str, str]] = [
    {
        "tag": "☕ Vibe Check",
        "emoji": "☕",
        "text": "Quick vibe check: are we waking up at 6 AM for sunrise spots or sleeping in and cafe-hopping? ☕"
    },
    {
        "tag": "🍕 Foodie Vibe",
        "emoji": "🍕",
        "text": "Be honest: authentic roadside street food or aesthetic rooftop cafes? Need to know if our travel energy matches haha!"
    },
    {
        "tag": "✨ Travel Style",
        "emoji": "✨",
        "text": "Crucial travel question: packed itinerary with zero downtime, or chill afternoons soaking in the views?"
    },
    {
        "tag": "🏔️ Trail Squad",
        "emoji": "🏔️",
        "text": "Fellow adventure lover! Are you more into mountain treks, coastal drives, or offbeat road trips?"
    },
    {
        "tag": "📸 Photo Vibe",
        "emoji": "📸",
        "text": "Bringing a camera along to shoot aesthetic views, or strictly traveling light with just your phone?"
    },
    {
        "tag": "🎒 Solo or Squad",
        "emoji": "🎒",
        "text": "Do you usually travel solo or roll with a squad? Always looking to connect with chill folks with similar travel vibes."
    },
    {
        "tag": "⏳ Trip Pace",
        "emoji": "⏳",
        "text": "Are you more of a spontaneous weekend escape person or a proper slow-travel planner?"
    },
    {
        "tag": "🤝 Split & Save",
        "emoji": "🤝",
        "text": "If our travel dates ever line up, totally down to split cabs or stays to keep costs friendly!"
    },
    {
        "tag": "🥾 Travel Energy",
        "emoji": "🥾",
        "text": "Action-packed exploring from dawn to dusk, or keeping things relaxed and scenic? What’s your ideal pace?"
    },
    {
        "tag": "🌲 Outdoor Vibe",
        "emoji": "🌲",
        "text": "Down for early morning hikes and exploring trails, or prefer keeping things strictly chill?"
    },
    {
        "tag": "🚗 Road Trip",
        "emoji": "🚗",
        "text": "Down for spontaneous road trips or scenic weekend drives if you're ever looking for travel companions!"
    }
]

# -------------------------------------------------------------
# 3. DISCOVERY & BUCKET LIST QUESTIONS (NO DESTINATION FORCED)
# -------------------------------------------------------------
DISCOVERY_STARTERS: List[Dict[str, str]] = [
    {
        "tag": "🗺️ Bucket List",
        "emoji": "🗺️",
        "text": "Hey {buddy_name}! What destination is sitting at the very top of your travel bucket list right now?"
    },
    {
        "tag": "🎒 Upcoming Trips",
        "emoji": "🎒",
        "text": "Planning any spontaneous weekend getaways soon, or saving up for a big bucket-list expedition?"
    },
    {
        "tag": "🌟 Hidden Gems",
        "emoji": "🌟",
        "text": "What's the best offbeat place or hidden gem you've traveled to so far? Always looking for inspiration!"
    },
    {
        "tag": "🏔️ Mountains or Sea",
        "emoji": "🏔️",
        "text": "If you had to pack a bag and leave tomorrow: mountain trails and chilly air, or sunny beaches and street food?"
    },
    {
        "tag": "🤝 Travel Squad",
        "emoji": "🤝",
        "text": "Always down to connect with fellow {badge} folks! Any dream trips you're trying to make happen this year?"
    },
    {
        "tag": "📸 Travel Moments",
        "emoji": "📸",
        "text": "Always love meeting people who travel for culture and great views. What’s your favorite trip memory so far?"
    },
    {
        "tag": "🧭 Next Adventure",
        "emoji": "🧭",
        "text": "Any upcoming trips on your radar for the next few months, or still deciding where to go?"
    }
]

# -------------------------------------------------------------
# 4. AGENT SIDE & CLIENT INQUIRY STARTERS
# -------------------------------------------------------------
# When Client asks Agent in chat:
CLIENT_TO_AGENT_STARTERS: List[Dict[str, str]] = [
    {
        "tag": "📦 Packages",
        "emoji": "📦",
        "text": "Hey {agent_name}! I'm looking to plan a trip to {destination}. Do you have customized packages or itineraries available?"
    },
    {
        "tag": "🌦️ Best Season",
        "emoji": "🌦️",
        "text": "Hi {agent_name}! What's the best season to visit {destination}, and what group sizes do you usually cater to?"
    },
    {
        "tag": "🏷️ Inclusions",
        "emoji": "🏷️",
        "text": "Hey! Are your upcoming departures to {destination} all-inclusive with stays, transport, and certified local guides?"
    },
    {
        "tag": "🗺️ Offbeat Itinerary",
        "emoji": "🗺️",
        "text": "Hi {agent_name}! Looking for recommendations on offbeat spots and must-visit landmarks around {destination}. What do you suggest?"
    },
    {
        "tag": "💰 Pricing & Dates",
        "emoji": "💰",
        "text": "Hey! Can you share pricing details, available departure dates, and itinerary options for a trip to {destination}?"
    },
    {
        "tag": "👥 Private Tours",
        "emoji": "👥",
        "text": "Hi {agent_name}! We're planning a trip soon — are customized private group departures or flexible dates possible?"
    },
    {
        "tag": "🚙 Transfers & Stays",
        "emoji": "🚙",
        "text": "Hi! Do your trips to {destination} include airport/station pickups and curated boutique stays?"
    },
    {
        "tag": "🎟️ Group Discount",
        "emoji": "🎟️",
        "text": "Hey {agent_name}! Do you offer early bird or group discounts for upcoming {destination} departures?"
    }
]

# When Agent responds / initiates with Client:
AGENT_TO_CLIENT_STARTERS: List[Dict[str, str]] = [
    {
        "tag": "👋 Welcome",
        "emoji": "👋",
        "text": "Hi {client_name}! Thanks for reaching out. I'd love to help you plan an unforgettable trip to {destination}. What dates are you looking at?"
    },
    {
        "tag": "📋 Itinerary Options",
        "emoji": "📋",
        "text": "Hello {client_name}! We have exciting customized itineraries and group departures for {destination}. How many travelers are in your group?"
    },
    {
        "tag": "🎯 Tailored Pace",
        "emoji": "🎯",
        "text": "Hi {client_name}! I can tailor the {destination} itinerary to your preferred pace — adventure-packed, scenic relaxation, or cultural exploring. What's your vibe?"
    },
    {
        "tag": "🛡️ Verified Service",
        "emoji": "🛡️",
        "text": "Hello! For {destination}, we take care of certified local guides, hand-picked stays, and seamless transfers. Would you like me to share a detailed day-wise plan?"
    },
    {
        "tag": "👥 Private or Group",
        "emoji": "👥",
        "text": "Hi {client_name}! Are you looking for a private customized tour to {destination} or interested in joining one of our curated group expeditions?"
    },
    {
        "tag": "💡 Seasonal Offers",
        "emoji": "💡",
        "text": "Hello {client_name}! Happy to share our exclusive package options and seasonal discounts for {destination}. What budget range do you have in mind?"
    },
    {
        "tag": "🗓️ Available Slots",
        "emoji": "🗓️",
        "text": "Hi {client_name}! If you have specific dates in mind for {destination}, let me know and I'll send over available slots and pricing right away!"
    },
    {
        "tag": "🏨 Stays & Logistics",
        "emoji": "🏨",
        "text": "Hello {client_name}! Let me know if you need help with boutique hotel options, flight timings, or permits for {destination}."
    }
]

# When in a Group Expedition Chat (e.g. Udaipur group trip):
GROUP_TRIP_STARTERS: List[Dict[str, str]] = [
    {
        "tag": "🎒 Group Vibe",
        "emoji": "🎒",
        "text": "Hey everyone! Super excited for our upcoming trip to {destination}! Has anyone visited {landmark} before?"
    },
    {
        "tag": "🗺️ Must-Visit Spots",
        "emoji": "🗺️",
        "text": "Hi squad! What spots or local food joints are sitting at the absolute top of everyone's list for {destination}?"
    },
    {
        "tag": "🛵 Rides & Transit",
        "emoji": "🛵",
        "text": "Are we planning to rent scooters or coordinate shared cabs once we all arrive in {destination}?"
    },
    {
        "tag": "🌅 Golden Hour",
        "emoji": "🌅",
        "text": "Down to catch the sunset at {landmark} together on one of the evenings! Who's in?"
    },
    {
        "tag": "☕ Morning Rhythm",
        "emoji": "☕",
        "text": "Quick vibe check for the group: waking up early for sunrise summits or keeping mornings relaxed with coffee?"
    },
    {
        "tag": "🏡 Stays & Rooms",
        "emoji": "🏡",
        "text": "Has everyone sorted their stay arrangements near {landmark} in {destination}, or coordinating together?"
    },
    {
        "tag": "🍜 Foodie Crawl",
        "emoji": "🍜",
        "text": "We definitely need to do a local food trail together in {destination}! Anyone know the best street food spots?"
    },
    {
        "tag": "✈️ Departure Dates",
        "emoji": "✈️",
        "text": "When is everyone reaching {destination}? Let's coordinate timings so we can meet up at the start!"
    }
]

# -------------------------------------------------------------
# LIGHTWEIGHT UNSAFE / SPAM LINK CLASSIFIER
# -------------------------------------------------------------
SUSPICIOUS_TLDS = {".tk", ".ml", ".ga", ".cf", ".gq", ".xyz", ".top", ".click", ".link", ".buzz", ".work"}
SUSPICIOUS_KEYWORDS = [
    "free crypto", "airdrop", "claim prize", "wire money", "verify account now",
    "lottery winner", "bit.ly/free", "tinyurl.com/prize", "earn money fast", "investment double"
]
URL_REGEX = re.compile(r'(?:https?://|www\.)[^\s/$.?#].[^\s]*', re.IGNORECASE)
IP_REGEX = re.compile(r'https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?::\d+)?(?:/[^\s]*)?', re.IGNORECASE)

def classify_message_safety(text: str) -> Dict[str, Any]:
    if not text or not isinstance(text, str):
        return {"is_safe": True, "flag_reason": None, "confidence": 1.0}

    lower_text = text.lower()
    if IP_REGEX.search(text):
        return {"is_safe": False, "flag_reason": "Suspicious raw IP address link detected", "confidence": 0.98}

    for kw in SUSPICIOUS_KEYWORDS:
        if kw in lower_text:
            return {"is_safe": False, "flag_reason": f"Suspicious phrasing detected: '{kw}'", "confidence": 0.92}

    urls = URL_REGEX.findall(text)
    for u in urls:
        u_lower = u.lower()
        for tld in SUSPICIOUS_TLDS:
            if tld in u_lower:
                return {"is_safe": False, "flag_reason": f"Untrusted domain extension '{tld}' detected", "confidence": 0.88}

    return {"is_safe": True, "flag_reason": None, "confidence": 0.99}


# -------------------------------------------------------------
# PROFILE ENTITY EXTRACTION
# -------------------------------------------------------------
def clean_entity(name: str) -> str:
    if not name:
        return ""
    cleaned = re.sub(r'^[^\w]+|[^\w]+$', '', name.strip())
    cleaned = re.sub(r'[^\w\s\-,]', '', cleaned).strip()
    return cleaned

def is_generic_destination(dest: str) -> bool:
    if not dest:
        return True
    cleaned = clean_entity(dest).lower()
    return cleaned in GENERIC_DESTS or len(cleaned) < 3

def extract_destinations(profile: Dict[str, Any]) -> List[str]:
    destinations = []
    
    # Direct destination property
    comp_dest = profile.get("destination") or profile.get("travel_destination") or profile.get("specializations")
    if comp_dest and isinstance(comp_dest, str):
        parts = [p.strip() for p in comp_dest.split(",")]
        for p in parts:
            d = clean_entity(p)
            if d and not is_generic_destination(d) and d not in destinations:
                destinations.append(d)

    # trip_interests
    interests = profile.get("trip_interests") or []
    if isinstance(interests, list):
        for item in interests:
            if isinstance(item, dict) and item.get("destination"):
                d = clean_entity(str(item.get("destination")))
                if d and not is_generic_destination(d) and d not in destinations:
                    destinations.append(d)
            elif isinstance(item, str) and item.strip():
                d = clean_entity(item)
                if d and not is_generic_destination(d) and d not in destinations:
                    destinations.append(d)

    # Check bio
    if not destinations:
        bio = profile.get("bio") or ""
        for key in DESTINATION_LANDMARKS.keys():
            if re.search(r'\b' + re.escape(key) + r'\b', bio, re.IGNORECASE):
                destinations.append(key.capitalize())
                break

    return destinations

def calculate_ngram_jaccard(str1: str, str2: str, n: int = 3) -> float:
    s1, s2 = str1.lower().strip(), str2.lower().strip()
    if s1 == s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    if s1 in s2 or s2 in s1:
        return 0.85

    ngrams1 = set([s1[i:i+n] for i in range(max(1, len(s1) - n + 1))])
    ngrams2 = set([s2[i:i+n] for i in range(max(1, len(s2) - n + 1))])
    union = len(ngrams1.union(ngrams2))
    if union == 0:
        return 0.0
    return len(ngrams1.intersection(ngrams2)) / float(union)

def find_mutual_destinations(user_dests: List[str], buddy_dests: List[str]) -> List[str]:
    """
    Finds all genuine matching destinations between two travelers.
    Returns empty list if there is no mutual overlap.
    """
    valid_ud = [d for d in (user_dests or []) if not is_generic_destination(d)]
    valid_bd = [d for d in (buddy_dests or []) if not is_generic_destination(d)]

    matches = []
    seen = set()
    for ud in valid_ud:
        for bd in valid_bd:
            sim = calculate_ngram_jaccard(ud, bd)
            if sim >= 0.45 or ud.lower() in bd.lower() or bd.lower() in ud.lower():
                best = bd if len(bd) <= len(ud) else ud
                cleaned = clean_entity(best)
                if cleaned and cleaned.lower() not in seen:
                    seen.add(cleaned.lower())
                    matches.append(cleaned)
    return matches

def find_mutual_destination(user_dests: List[str], buddy_dests: List[str]) -> Tuple[str, float]:
    """
    Returns the single best genuine matching destination between two travelers, or ('', 0.0) if none match.
    NEVER falls back to one-sided destinations.
    """
    valid_ud = [d for d in (user_dests or []) if not is_generic_destination(d)]
    valid_bd = [d for d in (buddy_dests or []) if not is_generic_destination(d)]

    best_dest = ""
    best_sim = 0.0

    for ud in valid_ud:
        for bd in valid_bd:
            sim = calculate_ngram_jaccard(ud, bd)
            if sim > best_sim:
                best_sim = sim
                best_dest = bd if len(bd) <= len(ud) else ud

    if best_sim >= 0.40 and best_dest:
        return best_dest, best_sim

    return "", 0.0

def get_landmark_for_destination(dest: str, seed: int = 0) -> str:
    if not dest or is_generic_destination(dest):
        return "the best scenic viewpoints and cafes"

    d_lower = dest.lower().strip()
    for key, landmarks in DESTINATION_LANDMARKS.items():
        if key in d_lower or d_lower in key:
            idx = (seed + random.randint(0, len(landmarks) - 1)) % len(landmarks)
            return landmarks[idx]

    idx = (seed + random.randint(0, len(GENERIC_LOCAL_SPOTS) - 1)) % len(GENERIC_LOCAL_SPOTS)
    return GENERIC_LOCAL_SPOTS[idx]

def find_shared_badge(user_badges: List[str], buddy_badges: List[str]) -> str:
    u_set = set([clean_entity(b).lower() for b in (user_badges or []) if b])
    b_set = set([clean_entity(b).lower() for b in (buddy_badges or []) if b])

    intersection = u_set.intersection(b_set)
    if intersection:
        matched = list(intersection)[0]
        for b in (buddy_badges or []) + (user_badges or []):
            if clean_entity(b).lower() == matched:
                return b

    if buddy_badges:
        return buddy_badges[0]
    if user_badges:
        return user_badges[0]

    return "🎒 Backpacker"


# -------------------------------------------------------------
# DYNAMIC ML & BALANCED MIXED CANDIDATE GENERATION ENGINE
# -------------------------------------------------------------
def rank_and_generate_icebreakers(
    user_profile: Dict[str, Any],
    buddy_profile: Dict[str, Any],
    vibe: str = "all",
    seed: int = 0,
    top_k: int = 15,
    override_destination: Optional[str] = None,
    role: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Generates a balanced, rich mix of conversation starters:
    - Multiple matching destinations rotated across place-related questions
    - General travel style & vibe questions (NO destination name forced)
    - Open bucket-list and upcoming trip discovery questions
    - Supports Agent operator and Client-to-Agent inquiry modes
    """
    user_name = (
        user_profile.get("first_name") or
        user_profile.get("user_name") or
        user_profile.get("name") or
        "Traveler"
    ).strip().split()[0]

    buddy_name = (
        buddy_profile.get("first_name") or
        buddy_profile.get("user_name") or
        buddy_profile.get("name") or
        buddy_profile.get("username") or
        "there"
    ).strip().split()[0]

    actual_seed = seed if seed != 0 else random.randint(1, 999999)
    rng = random.Random(actual_seed)

    # 1. Detect Role Mode
    # If role not explicitly passed, inspect profiles
    effective_role = (role or "").strip().lower()
    if not effective_role:
        if buddy_profile.get("role") == "agent" or "Verified Agent" in (buddy_profile.get("badges") or []):
            effective_role = "client_to_agent"
        elif user_profile.get("role") == "agent":
            effective_role = "agent_to_client"
        else:
            effective_role = "traveler"

    # 2. Extract Destinations & Find True Mutual Matches
    user_dests = extract_destinations(user_profile)
    buddy_dests = extract_destinations(buddy_profile)

    # In traveler mode: ONLY genuine matching destinations are used for place questions!
    # For group_trip or agent modes: use override_destination or expedition destination
    matching_dests: List[str] = []

    if effective_role == "group_trip":
        g_dest = override_destination or (buddy_profile.get("destination") or "")
        if g_dest and not is_generic_destination(g_dest):
            matching_dests.append(clean_entity(g_dest))
    elif effective_role in ["agent", "agent_to_client", "client_to_agent"]:
        if override_destination and not is_generic_destination(override_destination):
            matching_dests.append(clean_entity(override_destination))
        for d in buddy_dests + user_dests:
            c = clean_entity(d)
            if c and not is_generic_destination(c) and c.lower() not in [x.lower() for x in matching_dests]:
                matching_dests.append(c)
    else:
        # Traveler Mode: Genuine Mutual Overlap ONLY!
        if override_destination and not is_generic_destination(override_destination):
            matching_dests.append(clean_entity(override_destination))

        mutual_list = find_mutual_destinations(user_dests, buddy_dests)
        for m in mutual_list:
            if m.lower() not in [x.lower() for x in matching_dests]:
                matching_dests.append(m)

    primary_destination = matching_dests[0] if matching_dests else "your next destination"

    # Shared Badge
    u_badges = user_profile.get("badges") or []
    b_badges = buddy_profile.get("badges") or []
    badge = find_shared_badge(u_badges, b_badges)
    clean_badge = re.sub(r'^[^\w]+', '', badge).strip() or "Backpacker"

    # ---------------------------------------------------------
    # CASE: GROUP TRIP EXPEDITION CHAT (e.g. Udaipur group trip)
    # ---------------------------------------------------------
    if effective_role == "group_trip":
        shuffled = list(GROUP_TRIP_STARTERS)
        rng.shuffle(shuffled)
        out = []
        landmarks_for_dest = DESTINATION_LANDMARKS.get(primary_destination.lower().strip(), [])
        for idx, item in enumerate(shuffled):
            if landmarks_for_dest:
                chosen_spot = landmarks_for_dest[(idx + actual_seed) % len(landmarks_for_dest)]
            else:
                chosen_spot = GENERIC_LOCAL_SPOTS[(idx + actual_seed) % len(GENERIC_LOCAL_SPOTS)]
            formatted = item["text"].format(
                destination=primary_destination,
                landmark=chosen_spot,
                badge=clean_badge
            )
            out.append({
                "tag": item["tag"],
                "emoji": item["emoji"],
                "text": formatted,
                "category": "group"
            })
        return out[:top_k]

    # ---------------------------------------------------------
    # CASE A: AGENT OPERATOR MODE (Agent messaging a Client)
    # ---------------------------------------------------------
    if effective_role in ["agent", "agent_to_client"]:
        shuffled = list(AGENT_TO_CLIENT_STARTERS)
        rng.shuffle(shuffled)
        out = []
        for item in shuffled:
            formatted = item["text"].format(
                client_name=buddy_name,
                buddy_name=buddy_name,
                destination=primary_destination
            )
            out.append({
                "tag": item["tag"],
                "emoji": item["emoji"],
                "text": formatted,
                "category": "agent"
            })
        return out[:top_k]

    # ---------------------------------------------------------
    # CASE B: CLIENT TO AGENT MODE (Traveler inquiring with Agent)
    # ---------------------------------------------------------
    if effective_role == "client_to_agent":
        shuffled = list(CLIENT_TO_AGENT_STARTERS)
        rng.shuffle(shuffled)
        out = []
        for item in shuffled:
            formatted = item["text"].format(
                agent_name=buddy_name,
                destination=primary_destination
            )
            out.append({
                "tag": item["tag"],
                "emoji": item["emoji"],
                "text": formatted,
                "category": "inquiry"
            })
        return out[:top_k]

    # ---------------------------------------------------------
    # CASE C: TRAVELER TO TRAVELER (Balanced Mixed Mode)
    # ---------------------------------------------------------
    place_candidates = []
    if matching_dests:
        shuffled_place = list(PLACE_STARTERS)
        rng.shuffle(shuffled_place)
        for idx, item in enumerate(shuffled_place):
            # ROTATE across all matching destinations!
            target_dest = matching_dests[idx % len(matching_dests)]
            landmarks_for_dest = DESTINATION_LANDMARKS.get(target_dest.lower().strip(), [])
            if landmarks_for_dest:
                chosen_spot = landmarks_for_dest[(idx + actual_seed) % len(landmarks_for_dest)]
            else:
                chosen_spot = GENERIC_LOCAL_SPOTS[(idx + actual_seed) % len(GENERIC_LOCAL_SPOTS)]

            formatted = item["text"].format(
                buddy_name=buddy_name,
                destination=target_dest,
                landmark=chosen_spot,
                badge=clean_badge
            )
            place_candidates.append({
                "tag": item["tag"],
                "emoji": item["emoji"],
                "text": formatted,
                "category": "place"
            })

    # General Style Questions (NO destination forced)
    style_candidates = []
    shuffled_style = list(STYLE_STARTERS)
    rng.shuffle(shuffled_style)
    for item in shuffled_style:
        formatted = item["text"].format(
            buddy_name=buddy_name,
            badge=clean_badge
        )
        style_candidates.append({
            "tag": item["tag"],
            "emoji": item["emoji"],
            "text": formatted,
            "category": "style"
        })

    # Open Bucket List & Discovery Questions (NO destination forced)
    discovery_candidates = []
    shuffled_discovery = list(DISCOVERY_STARTERS)
    rng.shuffle(shuffled_discovery)
    for item in shuffled_discovery:
        formatted = item["text"].format(
            buddy_name=buddy_name,
            badge=clean_badge
        )
        discovery_candidates.append({
            "tag": item["tag"],
            "emoji": item["emoji"],
            "text": formatted,
            "category": "discovery"
        })

    # INTERLEAVE for a natural, rich mixture:
    # [Place (Dest 1), Style (No dest), Discovery (No dest), Place (Dest 2), Style (No dest)...]
    mixed_candidates = []
    p_i, s_i, d_i = 0, 0, 0

    while len(mixed_candidates) < top_k and (p_i < len(place_candidates) or s_i < len(style_candidates) or d_i < len(discovery_candidates)):
        # 1. Place / Local Question (if destinations exist)
        if p_i < len(place_candidates) and len(mixed_candidates) < top_k:
            mixed_candidates.append(place_candidates[p_i])
            p_i += 1

        # 2. General Style & Vibe (No destination forced)
        if s_i < len(style_candidates) and len(mixed_candidates) < top_k:
            mixed_candidates.append(style_candidates[s_i])
            s_i += 1

        # 3. Open Discovery / Bucket List (No destination forced)
        if d_i < len(discovery_candidates) and len(mixed_candidates) < top_k:
            mixed_candidates.append(discovery_candidates[d_i])
            d_i += 1

    return mixed_candidates[:top_k]
