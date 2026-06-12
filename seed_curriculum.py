"""
Seed script — curriculum_groups + curriculum_items
Populates ALL known columns with realistic chapter / unit / lesson data.

Boards:  CBSE/NCERT (Grades 1-12), ICSE (1-10), ISC (11-12),
         Maharashtra (1-12), Karnataka (1-12), Tamil Nadu (1-12)

Usage:
    python seed_curriculum.py

Requires env vars: SUPABASE_URL, SUPABASE_KEY
"""

import os, sys, uuid

try:
    from curriculum_importer import load_supabase_env_from_registry
except ImportError:
    def load_supabase_env_from_registry(): pass

try:
    from supabase import create_client
except ImportError:
    print("ERROR: run  pip install supabase")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _uid(): return str(uuid.uuid4())

def _keywords(text: str, n: int = 8):
    words = [w for w in text.lower().split() if len(w) > 2]
    seen, out = set(), []
    for w in words:
        if w not in seen:
            seen.add(w); out.append(w)
        if len(out) >= n: break
    return out

def _upsert_group(sb, board: dict) -> str:
    rows = (sb.table("curriculum_groups")
              .select("id").eq("code", board["code"]).limit(1).execute().data)
    if rows:
        gid = str(rows[0]["id"])
        sb.table("curriculum_groups").update({
            "name": board["name"], "description": board["description"], "status": "active",
        }).eq("id", gid).execute()
        print(f"  group updated  : {board['code']}  ({gid})")
        return gid
    gid = _uid()
    sb.table("curriculum_groups").insert({**board, "id": gid}).execute()
    print(f"  group inserted : {board['code']}  ({gid})")
    return gid

def _batch_insert(sb, rows: list, batch: int = 80) -> int:
    saved = 0
    for i in range(0, len(rows), batch):
        chunk = rows[i:i+batch]
        try:
            sb.table("curriculum_items").insert(chunk).execute()
            saved += len(chunk)
        except Exception:
            for r in chunk:
                try:
                    sb.table("curriculum_items").insert(r).execute()
                    saved += 1
                except Exception:
                    pass
    return saved

def make_row(gid, src_id, grade, grade_code, subject, textbook,
             unit_no, unit_title, lesson_no, lesson_title, objectives):
    desc = f"{lesson_title}. {' '.join(objectives[:2])}" if objectives else lesson_title
    return {
        "id": _uid(),
        "curriculum_group_id": gid,
        "source_id": src_id,
        "grade": grade,
        "grade_code": grade_code,
        "grade_sort_order": grade,
        "subject": subject,
        "unit_no": unit_no,
        "unit_title": unit_title,
        "lesson_no": lesson_no,
        "lesson_title": lesson_title,
        "description": desc,
        "item_type": "lesson",
        "status": "active",
        "source_section": unit_title,
        "source_reference": f"{grade_code}:{subject}:U{unit_no}:L{lesson_no}",
        "learning_objectives": objectives,
        "keywords": _keywords(f"{lesson_title} {subject} {unit_title}"),
        "meta": {
            "grade_label": grade_code,
            "textbook": textbook,
            "unit_no": unit_no,
            "lesson_no": lesson_no,
            "heading": lesson_title,
        },
    }

# ─────────────────────────────────────────────────────────────────────────────
# Board definitions
# ─────────────────────────────────────────────────────────────────────────────

BOARDS = [
    {"code": "CBSE",     "name": "Central Board of Secondary Education",   "country_code": "IN", "status": "active", "description": "NCERT-based national curriculum, Grades 1–12"},
    {"code": "ICSE",     "name": "Indian Certificate of Secondary Education", "country_code": "IN", "status": "active", "description": "CISCE board – Grades 1–10"},
    {"code": "ISC",      "name": "Indian School Certificate",              "country_code": "IN", "status": "active", "description": "CISCE senior secondary board – Grades 11–12"},
    {"code": "MH_STATE", "name": "Maharashtra State Board",                "country_code": "IN", "status": "active", "description": "Maharashtra SSC/HSC Board"},
    {"code": "KA_STATE", "name": "Karnataka State Board",                  "country_code": "IN", "status": "active", "description": "KSEEB – Karnataka Secondary Education"},
    {"code": "TN_STATE", "name": "Tamil Nadu State Board",                 "country_code": "IN", "status": "active", "description": "Samacheer Kalvi – Tamil Nadu"},
]

# ─────────────────────────────────────────────────────────────────────────────
# CBSE / NCERT  (Grades 1–12)
# Each entry: (grade, grade_code, subject, textbook, unit_no, unit_title, [(lesson_no, lesson_title, [objectives])])
# ─────────────────────────────────────────────────────────────────────────────

CBSE_DATA = [

# ══ Grades 1–5 (Primary) ══════════════════════════════════════════════════════

(1,"1","English","Marigold", 1,"Unit 1 – Greetings & Family",[
    (1,"A Happy Child",["Recite the poem with correct rhythm","Identify feelings of happiness","Use simple greeting words"]),
    (2,"Three Little Pigs",["Listen to a short story and recall events","Identify characters in a story","Retell story in own words"]),
]),
(1,"1","English","Marigold", 2,"Unit 2 – Nature & Animals",[
    (3,"Once I Saw a Little Bird",["Recognise common birds","Describe bird behaviour","Read a short poem aloud"]),
    (4,"Lalu and Peelu",["Identify colours in context","Match colours to objects","Answer simple comprehension questions"]),
]),
(1,"1","Mathematics","Math Magic", 1,"Unit 1 – Numbers to 9",[
    (1,"Shapes and Space",["Identify basic 2D and 3D shapes","Describe position using spatial words","Sort objects by shape"]),
    (2,"Numbers from One to Nine",["Count objects up to 9","Write numerals 1–9","Compare groups using more/less"]),
]),
(1,"1","Mathematics","Math Magic", 2,"Unit 2 – Operations",[
    (3,"Addition",["Add single-digit numbers","Use objects to add","Write simple addition sentences"]),
    (4,"Subtraction",["Subtract single-digit numbers","Understand the concept of 'taking away'","Relate addition and subtraction"]),
]),
(1,"1","EVS","Looking Around", 1,"Unit 1 – My World",[
    (1,"My Family",["Name family members","Describe family roles","Draw and label a family tree"]),
    (2,"My School",["Identify parts of the school","Name school helpers","Follow classroom rules"]),
]),

(2,"2","English","Marigold", 1,"Unit 1 – Fun & Friends",[
    (1,"First Day at School",["Describe feelings on a new day","Read a short story fluently","Answer who/what/where questions"]),
    (2,"I am Lucky!",["Identify things to be grateful for","Use adjectives to describe emotions","Compose 2–3 sentences about self"]),
]),
(2,"2","Mathematics","Math Magic", 1,"Unit 1 – Numbers & Operations",[
    (1,"Counting in Groups",["Count objects in groups of 2, 5, 10","Skip count forward and backward","Relate grouping to multiplication readiness"]),
    (2,"Tens and Ones",["Understand place value to 99","Represent two-digit numbers with blocks","Compare and order two-digit numbers"]),
]),
(2,"2","EVS","Looking Around", 1,"Unit 1 – Living World",[
    (1,"Plants Around Us",["Name common plants in the neighbourhood","Differentiate trees, shrubs and herbs","Describe the uses of plants"]),
    (2,"Animals Around Us",["Name domestic and wild animals","Identify the sounds animals make","Describe what animals eat"]),
]),

(3,"3","English","Marigold", 1,"Unit 1 – Stories & Poems",[
    (1,"Good Morning",["Recite the poem expressively","Greet others appropriately","Write a simple morning routine"]),
    (2,"The Magic Garden",["Identify the sequence of events","Understand cause and effect in a story","Write five sentences about plants"]),
]),
(3,"3","Mathematics","Math Magic", 1,"Unit 1 – Numbers & Operations",[
    (1,"Where to Look For?",["Read and write numbers up to 1000","Identify patterns in a number grid","Use number line to add/subtract"]),
    (2,"Fun with Numbers",["Order numbers up to 999","Round numbers to nearest 10","Estimate quantities"]),
]),
(3,"3","EVS","Looking Around", 1,"Unit 1 – Plants & Animals",[
    (1,"The Plant Fairy",["Identify parts of a plant","Explain the function of each part","Describe the conditions for plant growth"]),
    (2,"From the Window",["Observe changes in the environment","Describe seasonal changes","Record observations in a table"]),
]),

(4,"4","English","Marigold", 1,"Unit 1 – Adventure",[
    (1,"Wake Up!",["Understand the theme of responsibility","Identify rhyming words","Write an alternative ending to the poem"]),
    (2,"Neha's Alarm Clock",["Describe a daily schedule","Use time-related vocabulary","Write a paragraph about morning routine"]),
]),
(4,"4","Mathematics","Math Magic", 1,"Unit 1 – Geometry & Numbers",[
    (1,"Building with Bricks",["Identify 3D shapes from everyday objects","Count faces edges and vertices","Draw a simple building design"]),
    (2,"Long and Short",["Estimate and measure length","Use standard and non-standard units","Compare lengths using <, >, ="]),
]),
(4,"4","EVS","Looking Around", 1,"Unit 1 – My Environment",[
    (1,"Going to School",["Describe different modes of transport to school","Identify road safety rules","Draw and label a map of the route to school"]),
    (2,"Ear to Ear",["Understand different forms of communication","Compare old and new communication methods","Write a short telephone conversation"]),
]),

(5,"5","English","Marigold", 1,"Unit 1 – Imagination",[
    (1,"Ice-Cream Man",["Identify the mood of the poem","Describe sensory details","Write a poem about a favourite food"]),
    (2,"Wonderful Waste!",["Understand the concept of recycling","Identify waste materials and their reuse","Design a poster on waste management"]),
]),
(5,"5","Mathematics","Math Magic", 1,"Unit 1 – Numbers & Patterns",[
    (1,"The Fish Tale",["Interpret a story with numbers","Solve word problems involving large numbers","Create a data table from given information"]),
    (2,"Shapes and Angles",["Identify acute, obtuse and right angles","Classify triangles by angles","Measure angles with a protractor"]),
]),
(5,"5","EVS","Looking Around", 1,"Unit 1 – Living World",[
    (1,"Super Senses",["Explain how animals use their senses","Compare human and animal senses","Conduct a simple observation experiment"]),
    (2,"Seeds and Seeds",["Describe seed dispersal methods","Identify seeds by appearance","Germinate a seed and record observations"]),
]),

# ══ Grade 6 ═══════════════════════════════════════════════════════════════════

(6,"6","Mathematics","NCERT Mathematics", 1,"Unit I – Number System",[
    (1,"Knowing Our Numbers",["Read and write numbers up to crores","Compare and order large numbers","Round numbers to nearest thousand"]),
    (2,"Whole Numbers",["Identify properties of whole numbers","Apply commutative and associative properties","Represent numbers on a number line"]),
    (3,"Playing with Numbers",["Find factors and multiples","Determine HCF and LCM","Apply divisibility rules"]),
]),
(6,"6","Mathematics","NCERT Mathematics", 2,"Unit II – Algebra",[
    (4,"Basic Geometrical Ideas",["Define point, line, line segment and ray","Identify angles and their types","Construct basic geometric figures"]),
    (5,"Understanding Elementary Shapes",["Measure and compare angles","Classify triangles and quadrilaterals","Identify 3D shapes in the environment"]),
    (6,"Integers",["Understand positive and negative integers","Add and subtract integers on a number line","Apply integers in real-life contexts"]),
]),
(6,"6","Mathematics","NCERT Mathematics", 3,"Unit III – Fractions & Data",[
    (7,"Fractions",["Identify proper, improper and mixed fractions","Compare fractions with same and different denominators","Add and subtract like fractions"]),
    (8,"Decimals",["Read and write decimal numbers","Convert fractions to decimals and vice versa","Add and subtract decimals"]),
    (9,"Data Handling",["Collect and organise data in tables","Draw bar graphs and pictographs","Interpret graphs and draw conclusions"]),
]),

(6,"6","Science","NCERT Science", 1,"Unit I – Food",[
    (1,"Food: Where Does It Come From?",["Identify plant and animal sources of food","Classify animals as herbivores, carnivores, omnivores","List ingredients in common foods"]),
    (2,"Components of Food",["Name the nutrients in food","Describe the function of each nutrient","Test foods for starch, protein and fat"]),
    (3,"Fibre to Fabric",["Trace the journey from plant fibre to cloth","Distinguish between natural and synthetic fibres","Describe spinning and weaving processes"]),
]),
(6,"6","Science","NCERT Science", 2,"Unit II – Materials",[
    (4,"Sorting Materials into Groups",["Group objects by properties like texture and hardness","Distinguish between soluble and insoluble substances","Classify materials as transparent, translucent or opaque"]),
    (5,"Separation of Substances",["Describe methods of separation — sieving, filtration, evaporation","Apply the correct method based on mixture type","Explain why separation is necessary"]),
    (6,"Changes Around Us",["Distinguish reversible from irreversible changes","Give examples of physical and chemical changes","Explain factors that speed up or slow down change"]),
]),
(6,"6","Science","NCERT Science", 3,"Unit III – Living World",[
    (7,"Getting to Know Plants",["Identify parts of a plant and their functions","Differentiate herbs, shrubs and trees","Describe how roots absorb water"]),
    (8,"Body Movements",["Name major bones and joints","Identify types of joints and their movement","Describe how muscles and bones work together"]),
    (9,"The Living Organisms and Their Surroundings",["Define habitat and adaptation","Describe adaptations in desert, aquatic and polar organisms","Explain the meaning of biotic and abiotic factors"]),
]),
(6,"6","Science","NCERT Science", 4,"Unit IV – Physics",[
    (10,"Motion and Measurement of Distances",["Measure length using standard units","Convert between SI units","Distinguish between different types of motion"]),
    (11,"Light, Shadows and Reflections",["Explain how shadows are formed","Describe the law of reflection","Distinguish between transparent and opaque objects"]),
    (12,"Electricity and Circuits",["Identify components of an electric circuit","Distinguish between conductors and insulators","Draw and assemble a simple circuit"]),
    (13,"Fun with Magnets",["Identify poles of a magnet","Describe magnetic attraction and repulsion","List uses of magnets in daily life"]),
]),

(6,"6","Social Science","Our Pasts – I", 1,"Unit I – Ancient India",[
    (1,"What, Where, How and When?",["Explain what history is and why we study it","Identify sources of historical knowledge","Interpret simple timelines and dates"]),
    (2,"On the Trail of the Earliest People",["Describe how early humans lived","Identify evidence from archaeological sites","Explain the significance of the Stone Age"]),
    (3,"From Gathering to Growing Food",["Describe the transition from hunter-gatherer to farming","Identify early agricultural settlements","Explain why people settled near rivers"]),
    (4,"In the Earliest Cities",["Describe features of the Harappan civilisation","Identify important sites: Mohenjo-daro, Harappa","Explain why the civilisation declined"]),
]),
(6,"6","Social Science","The Earth: Our Habitat", 2,"Unit II – Geography",[
    (5,"The Earth in the Solar System",["Name the planets in order from the Sun","Explain the difference between a star and a planet","Describe the movements of the Earth"]),
    (6,"Globe: Latitudes and Longitudes",["Define latitude and longitude","Locate a place using co-ordinates","Explain the significance of the Equator and Prime Meridian"]),
    (7,"Motions of the Earth",["Distinguish between rotation and revolution","Explain day and night using rotation","Describe seasons caused by revolution"]),
    (8,"Maps",["Identify types of maps","Interpret a map using scale and symbols","Draw a simple sketch map"]),
]),
(6,"6","Social Science","Social and Political Life – I", 3,"Unit III – Civics",[
    (9,"Understanding Diversity",["Define diversity and give examples","Explain how diversity enriches society","Identify challenges that diversity may pose"]),
    (10,"Diversity and Discrimination",["Define discrimination","Describe the effects of discrimination","Discuss the importance of equality"]),
    (11,"What is Government?",["Define government and its levels","Explain why we need a government","Name the three tiers of government in India"]),
]),
(6,"6","English","Honeysuckle", 1,"Unit I – People & Values",[
    (1,"Who Did Patrick's Homework?",["Identify the moral of the story","Describe the character of Patrick","Write a paragraph about the importance of doing one's own work"]),
    (2,"How the Dog Found Himself a New Master!",["Summarise the plot","Explain why the dog chose the master","Discuss the theme of loyalty"]),
    (3,"Taro's Reward",["Identify the theme of filial piety","Describe the sequence of events","Use past tense verbs from the story"]),
]),

# ══ Grade 7 ═══════════════════════════════════════════════════════════════════

(7,"7","Mathematics","NCERT Mathematics", 1,"Unit I – Numbers",[
    (1,"Integers",["Perform all four operations on integers","Apply order of operations","Solve word problems using integers"]),
    (2,"Fractions and Decimals",["Multiply and divide fractions","Multiply and divide decimals","Solve multi-step problems with fractions and decimals"]),
    (3,"Data Handling",["Find mean, median and mode","Represent data in bar graphs and circle graphs","Interpret data from graphs"]),
]),
(7,"7","Mathematics","NCERT Mathematics", 2,"Unit II – Algebra & Geometry",[
    (4,"Simple Equations",["Translate word problems into equations","Solve one-step linear equations","Verify the solution of an equation"]),
    (5,"Lines and Angles",["Identify complementary and supplementary angles","Apply properties of parallel lines cut by a transversal","Prove that the sum of angles in a triangle is 180°"]),
    (6,"The Triangle and Its Properties",["Name and classify triangles","Apply the exterior angle property","Use the Pythagoras property in right triangles"]),
]),
(7,"7","Science","NCERT Science", 1,"Unit I – Nutrition",[
    (1,"Nutrition in Plants",["Explain photosynthesis","Describe heterotrophic nutrition","Give examples of insectivorous plants"]),
    (2,"Nutrition in Animals",["Describe the human digestive system","Explain the role of each digestive organ","Compare digestion in different animals"]),
]),
(7,"7","Science","NCERT Science", 2,"Unit II – Materials",[
    (3,"Fibre to Fabric",["Describe the life cycle of a silkworm","Explain the process of obtaining wool from sheep","Distinguish between natural and synthetic fibres"]),
    (4,"Heat",["Differentiate between heat and temperature","Describe conduction, convection and radiation","Explain why different materials have different conductivity"]),
    (5,"Acids, Bases and Salts",["Classify substances as acid, base or neutral","Use indicators to identify acids and bases","Describe neutralisation with examples"]),
]),
(7,"7","Science","NCERT Science", 3,"Unit III – Living World",[
    (6,"Physical and Chemical Changes",["Distinguish physical from chemical changes","Describe rusting and crystallisation","Identify signs of a chemical reaction"]),
    (7,"Weather, Climate and Adaptations",["Differentiate weather from climate","Describe climate types and their locations","Explain how animals adapt to different climates"]),
    (8,"Soil",["Describe how soil is formed","Identify layers of soil","Explain the importance of soil for agriculture"]),
]),
(7,"7","Social Science","Our Pasts – II", 1,"Unit I – Medieval India",[
    (1,"Tracing Changes Through a Thousand Years",["Explain how historians use sources from medieval India","Describe changes in administration and society","Identify key features of the medieval period"]),
    (2,"New Kings and Kingdoms",["Name the new dynasties that emerged after the Guptas","Describe feudalism in early medieval India","Explain land grants and their impact"]),
    (3,"The Delhi Sultans",["List the five dynasties of the Delhi Sultanate","Describe the administrative system of the Sultanate","Explain the importance of the Sultanate period"]),
    (4,"The Mughal Empire",["Describe the major Mughal emperors","Explain the administrative structure of the Mughal Empire","Discuss the decline of the Mughal Empire"]),
]),

# ══ Grade 8 ═══════════════════════════════════════════════════════════════════

(8,"8","Mathematics","NCERT Mathematics", 1,"Unit I – Number System",[
    (1,"Rational Numbers",["Represent rational numbers on a number line","Perform operations on rational numbers","Find rational numbers between two given numbers"]),
    (2,"Linear Equations in One Variable",["Solve linear equations with variables on both sides","Convert word problems to equations","Verify solutions"]),
]),
(8,"8","Mathematics","NCERT Mathematics", 2,"Unit II – Geometry",[
    (3,"Understanding Quadrilaterals",["Define and classify quadrilaterals","Apply angle-sum property","Identify properties of parallelograms and special quadrilaterals"]),
    (4,"Practical Geometry",["Construct quadrilaterals given sufficient information","Use compass and ruler accurately","Verify constructions"]),
]),
(8,"8","Mathematics","NCERT Mathematics", 3,"Unit III – Mensuration",[
    (5,"Mensuration",["Find area of trapezium and general quadrilaterals","Calculate surface area of cube, cuboid and cylinder","Find volume of cube, cuboid and cylinder"]),
    (6,"Squares and Square Roots",["Find square and square root of numbers","Use patterns to find squares","Apply square roots to solve problems"]),
    (7,"Cubes and Cube Roots",["Find cubes and cube roots","Identify perfect cubes","Apply cube roots in problem solving"]),
]),
(8,"8","Science","NCERT Science", 1,"Unit I – Food & Materials",[
    (1,"Crop Production and Management",["Describe agricultural practices: preparation, sowing, irrigation","Explain the role of fertilisers and pesticides","Describe harvesting and storage methods"]),
    (2,"Microorganisms: Friend and Foe",["Classify microorganisms","Describe beneficial uses of microorganisms","Explain diseases caused by microorganisms"]),
    (3,"Synthetic Fibres and Plastics",["Classify synthetic fibres","Describe properties of synthetic materials","Discuss environmental impact of plastics"]),
]),
(8,"8","Science","NCERT Science", 2,"Unit II – Living World",[
    (4,"Cell – Structure and Functions",["Describe the structure of plant and animal cells","Identify the function of each organelle","Distinguish between unicellular and multicellular organisms"]),
    (5,"Reproduction in Animals",["Differentiate sexual and asexual reproduction","Describe the human reproductive process","Explain metamorphosis in insects"]),
    (6,"Reaching the Age of Adolescence",["Define adolescence and puberty","Describe physical and hormonal changes during puberty","Discuss personal hygiene and reproductive health"]),
]),
(8,"8","Social Science","Our Pasts – III", 1,"Unit I – How, When and Where",[
    (1,"How, When and Where",["Explain how history is organised by dates","Describe colonial administration in India","Identify sources for writing modern Indian history"]),
    (2,"From Trade to Territory",["Describe how the British East India Company expanded","Explain the Battle of Plassey","Discuss British policies that led to their dominance"]),
    (3,"Ruling the Countryside",["Explain the Permanent Settlement","Describe how indigo was cultivated","Discuss the impact of British land policies"]),
]),

# ══ Grade 9 ═══════════════════════════════════════════════════════════════════

(9,"9","Mathematics","NCERT Mathematics", 1,"Unit I – Number Systems",[
    (1,"Number Systems",["Classify numbers as natural, whole, integer, rational, irrational","Represent irrational numbers on the number line","Apply laws of exponents to real numbers"]),
]),
(9,"9","Mathematics","NCERT Mathematics", 2,"Unit II – Algebra",[
    (2,"Polynomials",["Define polynomial and its degree","Apply remainder theorem and factor theorem","Factorise polynomials using algebraic identities"]),
    (3,"Linear Equations in Two Variables",["Express a linear equation in two variables","Find solutions and represent them graphically","Interpret graphs of linear equations"]),
]),
(9,"9","Mathematics","NCERT Mathematics", 3,"Unit III – Geometry",[
    (4,"Lines and Angles",["Identify pairs of angles formed by parallel lines and a transversal","Apply the angle-sum property of a triangle","Prove theorems on lines and angles"]),
    (5,"Triangles",["State congruence criteria: SSS, SAS, ASA, RHS","Apply properties of isosceles triangles","Prove the inequalities in a triangle"]),
    (6,"Quadrilaterals",["State and apply properties of parallelograms","Apply the mid-point theorem","Prove properties of special parallelograms"]),
    (7,"Circles",["Define circle and its parts","Apply theorems on chords and angles in a circle","Prove angle-in-a-semicircle is 90°"]),
]),
(9,"9","Mathematics","NCERT Mathematics", 4,"Unit IV – Mensuration & Statistics",[
    (8,"Heron's Formula",["State Heron's formula","Calculate area of a triangle using Heron's formula","Apply formula to quadrilaterals"]),
    (9,"Surface Areas and Volumes",["Find surface area of cube, cuboid, cylinder, cone, sphere","Find volume of the above solids","Solve word problems involving 3D shapes"]),
    (10,"Statistics",["Collect data and organise in frequency tables","Draw and interpret bar graphs, histograms and frequency polygons","Calculate mean, median and mode of ungrouped data"]),
]),
(9,"9","Science","NCERT Science", 1,"Unit I – Matter",[
    (1,"Matter in Our Surroundings",["Define matter and describe its states","Explain evaporation and its factors","Describe interconversion of states using diagrams"]),
    (2,"Is Matter Around Us Pure?",["Distinguish between elements, compounds and mixtures","Describe methods of separation","Differentiate physical from chemical properties"]),
    (3,"Atoms and Molecules",["State the laws of chemical combination","Define atomic mass and molecular mass","Write chemical formulae using valency"]),
    (4,"Structure of the Atom",["Describe Dalton's and Thomson's atomic models","Explain Bohr's model of the atom","Write electronic configuration for first 18 elements"]),
]),
(9,"9","Science","NCERT Science", 2,"Unit II – Organisation in Living World",[
    (5,"The Fundamental Unit of Life",["Describe cell as the basic unit of life","Identify organelles and their functions","Distinguish plant cell from animal cell"]),
    (6,"Tissues",["Define tissue","Compare plant and animal tissues","Explain the function of each type of tissue"]),
]),
(9,"9","Science","NCERT Science", 3,"Unit III – Motion, Force and Work",[
    (7,"Motion",["Define distance, displacement, speed and velocity","Plot and interpret distance-time and velocity-time graphs","Apply equations of uniformly accelerated motion"]),
    (8,"Force and Laws of Motion",["State Newton's three laws of motion","Define inertia and momentum","Apply the law of conservation of momentum"]),
    (9,"Gravitation",["State the universal law of gravitation","Distinguish between mass and weight","Explain free fall and Archimedes' principle"]),
    (10,"Work and Energy",["Define work, energy and power","State the law of conservation of energy","Distinguish between kinetic and potential energy"]),
    (11,"Sound",["Describe production and propagation of sound","Calculate speed of sound","Explain reflection of sound and echo"]),
]),
(9,"9","Social Science","India and the Contemporary World – I", 1,"Unit I – History",[
    (1,"The French Revolution",["Describe the causes of the French Revolution","Explain the main events of the Revolution","Discuss the legacy of the Revolution"]),
    (2,"Socialism in Europe and the Russian Revolution",["Describe socialist ideas in 19th-century Europe","Explain the causes and events of the Russian Revolution","Discuss the impact of the Russian Revolution on the world"]),
    (3,"Nazism and the Rise of Hitler",["Explain how Hitler came to power","Describe Nazi ideology and policies","Discuss the Holocaust and World War II"]),
]),
(9,"9","Social Science","Contemporary India – I", 2,"Unit II – Geography",[
    (4,"India – Size and Location",["Locate India on a world map","Describe the latitudinal and longitudinal extent of India","Explain the significance of India's location"]),
    (5,"Physical Features of India",["Identify the major physiographic divisions of India","Describe the Himalayas, peninsular plateau and coastal plains","Explain the formation of the Northern Plains"]),
    (6,"Drainage",["Describe the drainage system of India","Distinguish between Himalayan and Peninsular rivers","Explain the importance of rivers"]),
    (7,"Climate",["Describe the factors affecting climate of India","Explain the mechanism of the monsoon","Identify different seasons of India"]),
]),
(9,"9","Social Science","Democratic Politics – I", 3,"Unit III – Political Science",[
    (8,"What is Democracy? Why Democracy?",["Define democracy","List features of a democratic government","Compare democracy with other forms of government"]),
    (9,"Constitutional Design",["Explain the process of making the Indian Constitution","Describe the guiding values in the Preamble","Identify fundamental rights and their importance"]),
    (10,"Electoral Politics",["Describe the electoral system in India","Explain how elections are conducted","Discuss the role of the Election Commission"]),
]),
(9,"9","English","Beehive", 1,"Unit I – People & Experiences",[
    (1,"The Fun They Had",["Discuss the theme of technology in education","Compare traditional and futuristic schools","Write a diary entry"]),
    (2,"The Sound of Music",["Identify the themes of determination and passion","Describe the achievements of Evelyn Glennie and Bismillah Khan","Use contextual vocabulary in sentences"]),
    (3,"The Little Girl",["Analyse the relationship between Kezia and her father","Identify the turning point in the story","Write a character sketch of Kezia"]),
]),

# ══ Grade 10 ══════════════════════════════════════════════════════════════════

(10,"10","Mathematics","NCERT Mathematics", 1,"Unit I – Number Systems",[
    (1,"Real Numbers",["Prove irrationality of √2, √3, √5","State and apply Euclid's division lemma","Apply the fundamental theorem of arithmetic"]),
]),
(10,"10","Mathematics","NCERT Mathematics", 2,"Unit II – Algebra",[
    (2,"Polynomials",["Find zeros of quadratic and cubic polynomials","Verify relationship between zeros and coefficients","Divide one polynomial by another and find remainder"]),
    (3,"Pair of Linear Equations in Two Variables",["Solve a pair of linear equations graphically","Apply substitution and elimination methods","Solve cross-multiplication method"]),
    (4,"Quadratic Equations",["Solve quadratic equations by factorisation","Apply the quadratic formula","Use the discriminant to determine nature of roots"]),
    (5,"Arithmetic Progressions",["Identify an AP and find its common difference","Find the nth term of an AP","Find the sum of first n terms of an AP"]),
]),
(10,"10","Mathematics","NCERT Mathematics", 3,"Unit III – Geometry",[
    (6,"Triangles",["State and apply the basic proportionality theorem","Prove criteria for similarity of triangles","Apply Pythagoras' theorem and its converse"]),
    (7,"Coordinate Geometry",["Find distance between two points","Apply section formula to divide a line","Find area of a triangle using coordinates"]),
    (8,"Introduction to Trigonometry",["Define trigonometric ratios","Find trigonometric ratios for specific angles","Apply trigonometric identities"]),
    (9,"Some Applications of Trigonometry",["Explain angle of elevation and depression","Solve problems involving heights and distances","Apply trigonometric ratios in real-life contexts"]),
    (10,"Circles",["Define tangent to a circle","Prove the tangent-radius perpendicularity theorem","Apply properties of tangents drawn from an external point"]),
]),
(10,"10","Mathematics","NCERT Mathematics", 4,"Unit IV – Mensuration & Statistics",[
    (11,"Areas Related to Circles",["Calculate area of a sector and segment","Find area of combination of plane figures","Apply formulae to solve real-life problems"]),
    (12,"Surface Areas and Volumes",["Find surface area and volume of combinations of solids","Solve problems involving conversion of solids","Apply mensuration formulae in real-life contexts"]),
    (13,"Statistics",["Calculate mean by direct, assumed mean and step-deviation methods","Find median and mode from grouped data","Represent data with ogives"]),
    (14,"Probability",["Define probability","Find probability of simple events","Apply probability to everyday situations"]),
]),
(10,"10","Science","NCERT Science", 1,"Unit I – Chemical Substances",[
    (1,"Chemical Reactions and Equations",["Write and balance chemical equations","Classify reactions as combination, decomposition, displacement, double displacement","Identify oxidation and reduction in reactions"]),
    (2,"Acids, Bases and Salts",["Explain properties of acids and bases","Describe the pH scale and its uses","Describe manufacture of common salts"]),
    (3,"Metals and Non-metals",["Describe physical and chemical properties of metals","Explain reactivity series","Describe the extraction of metals from ores"]),
    (4,"Carbon and Its Compounds",["Describe bonding in carbon compounds","Explain homologous series","Name and draw structural formulae of hydrocarbons and functional groups"]),
]),
(10,"10","Science","NCERT Science", 2,"Unit II – World of the Living",[
    (5,"Life Processes",["Describe nutrition in autotrophs and heterotrophs","Explain the human respiratory and circulatory systems","Describe excretion in humans and plants"]),
    (6,"Control and Coordination",["Describe the human nervous system","Explain reflex action","Describe the role of hormones in the body"]),
    (7,"How do Organisms Reproduce?",["Distinguish asexual from sexual reproduction","Describe sexual reproduction in flowering plants","Describe human reproductive system"]),
    (8,"Heredity",["Explain Mendel's laws of heredity","Distinguish between inherited and acquired traits","Describe sex determination in humans"]),
]),
(10,"10","Science","NCERT Science", 3,"Unit III – Natural Phenomena",[
    (9,"Light – Reflection and Refraction",["Apply laws of reflection to plane and curved mirrors","Apply Snell's law of refraction","Derive the lens formula and apply it"]),
    (10,"The Human Eye and the Colourful World",["Describe the structure and function of the human eye","Explain accommodation and common vision defects","Describe dispersion and scattering of light"]),
]),
(10,"10","Science","NCERT Science", 4,"Unit IV – Effects of Current & Environment",[
    (11,"Electricity",["State Ohm's law and verify it","Calculate resistance in series and parallel","Apply Joule's law of heating"]),
    (12,"Magnetic Effects of Electric Current",["Describe magnetic field due to current","Explain electromagnetic induction","Describe AC and DC generators"]),
    (13,"Our Environment",["Describe food chains and food webs","Explain the flow of energy in an ecosystem","Discuss environmental problems: ozone depletion, waste management"]),
]),
(10,"10","Social Science","India and the Contemporary World – II", 1,"Unit I – History",[
    (1,"The Rise of Nationalism in Europe",["Explain the concept of nationalism","Describe the unification of Germany and Italy","Discuss the role of culture in nation-building"]),
    (2,"Nationalism in India",["Describe the Non-Cooperation Movement","Explain the Civil Disobedience Movement","Discuss the role of different groups in the national movement"]),
    (3,"The Making of a Global World",["Trace how the world became connected through trade","Explain the Great Depression and its effects","Describe post-war economic recovery"]),
    (4,"The Age of Industrialisation",["Describe proto-industrialisation","Explain the growth of factories in Britain","Discuss industrialisation in India"]),
]),
(10,"10","English","First Flight", 1,"Unit I – Stories of Courage",[
    (1,"A Letter to God",["Identify the theme of faith and simplicity","Describe the character of Lencho","Discuss the irony in the story"]),
    (2,"Nelson Mandela: Long Walk to Freedom",["Describe the life and struggles of Nelson Mandela","Explain the meaning of freedom and dignity","Identify values demonstrated by Mandela"]),
    (3,"Two Stories About Flying",["Compare the two stories about flight","Identify the theme of learning from experience","Discuss the relationship between humans and nature"]),
]),

# ══ Grade 11 ══════════════════════════════════════════════════════════════════

(11,"XI","Physics","NCERT Physics Part I", 1,"Unit I – Physical World & Kinematics",[
    (1,"Physical World",["Describe the scope of physics","Identify fundamental forces in nature","Explain the role of physics in technology"]),
    (2,"Units and Measurements",["State SI units for fundamental quantities","Use dimensional analysis to verify formulae","Estimate errors and uncertainties in measurements"]),
    (3,"Motion in a Straight Line",["Distinguish between distance and displacement","Derive equations of motion for uniform acceleration","Interpret distance-time and velocity-time graphs"]),
    (4,"Motion in a Plane",["Resolve vectors into components","Derive equations for projectile motion","Apply relative velocity concepts"]),
]),
(11,"XI","Physics","NCERT Physics Part I", 2,"Unit II – Laws of Motion & Work",[
    (5,"Laws of Motion",["State Newton's three laws of motion","Apply the concept of free body diagrams","Solve problems involving friction and circular motion"]),
    (6,"Work, Energy and Power",["Define work, energy and power","Apply the work-energy theorem","Distinguish elastic from inelastic collisions"]),
    (7,"System of Particles and Rotational Motion",["Define centre of mass and find it for a system","Apply the law of conservation of angular momentum","Calculate moment of inertia for simple bodies"]),
    (8,"Gravitation",["State Newton's law of universal gravitation","Derive expression for acceleration due to gravity","Describe orbital and escape velocity"]),
]),
(11,"XI","Physics","NCERT Physics Part II", 3,"Unit III – Properties of Matter & Thermodynamics",[
    (9,"Mechanical Properties of Solids",["Define stress and strain","State Hooke's law","Compare elastic moduli: Young's, bulk, shear"]),
    (10,"Mechanical Properties of Fluids",["State Pascal's law and Archimedes' principle","Apply Bernoulli's equation","Describe surface tension and capillarity"]),
    (11,"Thermal Properties of Matter",["Describe modes of heat transfer","Apply Newton's law of cooling","Explain thermal expansion"]),
    (12,"Thermodynamics",["State the first and second laws of thermodynamics","Describe isothermal, adiabatic, isobaric and isochoric processes","Explain the Carnot engine and efficiency"]),
    (13,"Kinetic Theory",["Derive the ideal gas law from kinetic theory","Define degrees of freedom","Explain the law of equipartition of energy"]),
]),
(11,"XI","Physics","NCERT Physics Part II", 4,"Unit IV – Oscillations & Waves",[
    (14,"Oscillations",["Define SHM and give examples","Derive equations for SHM","Explain energy in SHM"]),
    (15,"Waves",["Classify waves: transverse and longitudinal","State the principle of superposition","Explain resonance and standing waves"]),
]),

(11,"XI","Chemistry","NCERT Chemistry Part I", 1,"Unit I – Basic Concepts & Atomic Structure",[
    (1,"Some Basic Concepts of Chemistry",["Define mole concept and apply it","Calculate empirical and molecular formulae","Solve stoichiometric problems"]),
    (2,"Structure of Atom",["Describe models of the atom: Thomson, Rutherford, Bohr","Explain quantum numbers and orbitals","Write electronic configuration using Aufbau principle"]),
    (3,"Classification of Elements and Periodicity",["Explain the basis of the modern periodic table","Describe periodic trends: atomic radius, IE, EN","Predict properties of elements using periodicity"]),
]),
(11,"XI","Chemistry","NCERT Chemistry Part I", 2,"Unit II – Chemical Bonding & Thermodynamics",[
    (4,"Chemical Bonding and Molecular Structure",["Describe ionic and covalent bonding","Apply VSEPR theory to predict molecular geometry","Explain hybridisation and molecular orbital theory"]),
    (5,"Thermodynamics",["Define system, surroundings and state functions","Apply the first law of thermodynamics","Define and calculate enthalpy, entropy and Gibbs energy"]),
    (6,"Equilibrium",["State Le Chatelier's principle","Write Kc and Kp expressions","Solve equilibrium problems"]),
]),
(11,"XI","Chemistry","NCERT Chemistry Part II", 3,"Unit III – Organic Chemistry",[
    (7,"Redox Reactions",["Define oxidation and reduction in terms of electron transfer","Assign oxidation states","Balance redox equations by the half-reaction method"]),
    (8,"Organic Chemistry – Basic Principles",["Define organic compounds and functional groups","Apply IUPAC nomenclature to organic compounds","Describe types of organic reactions"]),
    (9,"Hydrocarbons",["Classify hydrocarbons: alkanes, alkenes, alkynes, arenes","Describe reactions of each class","Explain conformational and geometrical isomerism"]),
    (10,"Environmental Chemistry",["Describe types of environmental pollution","Explain the chemistry of stratospheric ozone depletion","Discuss green chemistry principles"]),
]),

(11,"XI","Biology","NCERT Biology", 1,"Unit I – Diversity in Living World",[
    (1,"The Living World",["Define life and list its characteristics","Explain the need for classification","Use binomial nomenclature correctly"]),
    (2,"Biological Classification",["Describe the five-kingdom classification","Characterise Monera, Protista and Fungi","Give examples of each kingdom"]),
    (3,"Plant Kingdom",["Classify plants from algae to angiosperms","Describe alternation of generations","Distinguish gymnosperms from angiosperms"]),
    (4,"Animal Kingdom",["Describe criteria for animal classification","Compare phyla: Porifera to Chordata","Give examples of animals in each phylum"]),
]),
(11,"XI","Biology","NCERT Biology", 2,"Unit II – Structural Organisation",[
    (5,"Morphology of Flowering Plants",["Identify parts of a flowering plant","Describe modifications of root, stem and leaf","Classify inflorescence and flowers"]),
    (6,"Anatomy of Flowering Plants",["Describe different types of plant tissues","Compare dicot and monocot anatomy","Explain secondary growth"]),
    (7,"Structural Organisation in Animals",["Classify animal tissues","Describe organ systems in earthworm, cockroach and frog","Explain histology of major organs"]),
]),
(11,"XI","Biology","NCERT Biology", 3,"Unit III – Cell",[
    (8,"Cell: The Unit of Life",["Describe the structure of prokaryotic and eukaryotic cells","Explain the function of cell organelles","Distinguish plant from animal cell"]),
    (9,"Biomolecules",["Classify biomolecules: carbohydrates, proteins, lipids, nucleic acids","Describe the structure and function of enzymes","Explain the concept of metabolism"]),
    (10,"Cell Cycle and Cell Division",["Describe the stages of the cell cycle","Compare mitosis and meiosis","Explain the significance of meiosis"]),
]),
(11,"XI","Biology","NCERT Biology", 4,"Unit IV – Plant Physiology",[
    (11,"Photosynthesis in Higher Plants",["Describe the structure of the chloroplast","Explain the light-dependent and light-independent reactions","Compare C3 and C4 pathways"]),
    (12,"Respiration in Plants",["Describe glycolysis and the Krebs cycle","Explain the electron transport chain","Calculate ATP yield from aerobic respiration"]),
    (13,"Plant Growth and Development",["Define growth and differentiation","Describe the role of plant hormones","Explain seed germination and dormancy"]),
]),
(11,"XI","Biology","NCERT Biology", 5,"Unit V – Human Physiology",[
    (14,"Breathing and Exchange of Gases",["Describe the mechanism of breathing","Explain transport of O2 and CO2 in blood","Describe respiratory volumes and capacities"]),
    (15,"Body Fluids and Circulation",["Describe the composition of blood","Explain the cardiac cycle","Describe the lymphatic system"]),
    (16,"Excretory Products and Their Elimination",["Describe the structure of the nephron","Explain urine formation","Describe accessory excretory organs"]),
    (17,"Locomotion and Movement",["Classify joints","Describe the sliding filament model","Explain disorders of the muscular and skeletal system"]),
    (18,"Neural Control and Coordination",["Describe the structure of a neuron","Explain nerve impulse transmission","Describe the human brain structure"]),
    (19,"Chemical Coordination and Integration",["Name endocrine glands and their hormones","Explain the regulation of hormone secretion","Describe diseases caused by hormonal imbalance"]),
]),

(11,"XI","Mathematics","NCERT Mathematics", 1,"Unit I – Sets & Functions",[
    (1,"Sets",["Define a set and represent it in roster and set-builder form","Perform union, intersection and complement operations","Apply De Morgan's laws"]),
    (2,"Relations and Functions",["Define relation and function","Determine domain, codomain and range","Classify functions: one-one, onto, bijective"]),
    (3,"Trigonometric Functions",["Convert between degrees and radians","Derive values of trigonometric functions for standard angles","Prove trigonometric identities"]),
]),
(11,"XI","Mathematics","NCERT Mathematics", 2,"Unit II – Algebra",[
    (4,"Complex Numbers and Quadratic Equations",["Represent complex numbers in standard form","Find modulus and conjugate of a complex number","Apply the quadratic formula to complex roots"]),
    (5,"Linear Inequalities",["Solve linear inequalities in one variable","Graph solutions on a number line","Solve systems of linear inequalities graphically"]),
    (6,"Permutations and Combinations",["State the fundamental counting principle","Calculate permutations and combinations","Solve problems using nPr and nCr"]),
    (7,"Binomial Theorem",["State the binomial theorem","Expand (a+b)n using the theorem","Find a specific term in a binomial expansion"]),
    (8,"Sequences and Series",["Identify arithmetic and geometric progressions","Find the nth term and sum of an AP and GP","Understand the sum of infinite GP"]),
]),
(11,"XI","Mathematics","NCERT Mathematics", 3,"Unit III – Coordinate Geometry",[
    (9,"Straight Lines",["Find slope from two points","Write equations of a line in various forms","Find distance between parallel lines"]),
    (10,"Conic Sections",["Define circle, parabola, ellipse and hyperbola","Derive the standard equation of each conic","Identify the conic from a given equation"]),
    (11,"Introduction to Three Dimensional Geometry",["Locate a point in 3D space using coordinates","Find distance between two points in 3D","Find the coordinates of a point dividing a segment"]),
]),
(11,"XI","Mathematics","NCERT Mathematics", 4,"Unit IV – Calculus & Statistics",[
    (12,"Limits and Derivatives",["Define the limit of a function","Calculate limits using standard results","Differentiate polynomial and trigonometric functions"]),
    (13,"Statistics",["Calculate mean, variance and standard deviation for ungrouped and grouped data","Apply the coefficient of variation","Compare variability of two data sets"]),
    (14,"Probability",["Define probability using classical and axiomatic approach","Apply addition and multiplication theorems","Solve problems involving conditional probability"]),
]),

(11,"XI","History","Themes in World History", 1,"Unit I – Early Societies & Empires",[
    (1,"From the Beginning of Time",["Describe the evolution of early humans","Explain the significance of stone tools","Discuss the move to sedentary life"]),
    (2,"Early Societies",["Describe hunter-gatherer societies","Explain the Neolithic revolution","Discuss early art and culture"]),
    (3,"An Empire Across Three Continents",["Describe the Roman Empire at its height","Explain its administrative and economic systems","Discuss factors leading to its decline"]),
    (4,"The Central Islamic Lands",["Trace the rise of Islam","Describe the Caliphate system","Explain the cultural contributions of Islamic civilisation"]),
]),
(11,"XI","Geography","Fundamentals of Physical Geography", 1,"Unit I – Geography as a Discipline",[
    (1,"Geography as a Discipline",["Define geography and its branches","Explain the relationship between physical and human geography","Describe methods used in geographical studies"]),
    (2,"Origin and Evolution of the Earth",["Describe the Big Bang theory","Explain the formation of the solar system","Describe how the Earth's structure evolved"]),
    (3,"Interior of the Earth",["Describe the layers of the Earth","Explain seismic waves and their types","Interpret a seismogram"]),
]),
(11,"XI","Economics","Statistics for Economics", 1,"Unit I – Statistics",[
    (1,"Introduction",["Define statistics and its importance","Distinguish between primary and secondary data","Identify different types of statistical data"]),
    (2,"Collection of Data",["Describe methods of data collection: questionnaire, interview","Distinguish between census and sample survey","Identify sources of secondary data"]),
    (3,"Organisation of Data",["Arrange raw data into frequency distributions","Determine class intervals","Distinguish between exclusive and inclusive classes"]),
    (4,"Presentation of Data",["Represent data using bar, pie and histogram","Draw frequency polygons and ogives","Interpret diagrams and graphs"]),
    (5,"Measures of Central Tendency",["Calculate arithmetic mean, median and mode","Apply weighted mean","Identify appropriate measure for different data"]),
    (6,"Measures of Dispersion",["Define range, quartile deviation, mean deviation and standard deviation","Calculate standard deviation for ungrouped data","Apply coefficient of variation"]),
]),

(11,"XI","Computer Science","NCERT Computer Science", 1,"Unit I – Computer Fundamentals",[
    (1,"Computer Overview",["Describe the evolution of computers","Identify hardware components and their functions","Explain the concept of operating systems"]),
    (2,"Software Concepts",["Distinguish system software from application software","Define open-source and proprietary software","Explain programming language levels"]),
]),
(11,"XI","Computer Science","NCERT Computer Science", 2,"Unit II – Programming in Python",[
    (3,"Getting Started with Python",["Install and run Python","Write and execute a simple Python program","Identify Python data types and variables"]),
    (4,"Flow of Control",["Use if-elif-else statements","Write for and while loops","Apply nested loops and break/continue"]),
    (5,"Functions",["Define and call a function","Explain scope and lifetime of variables","Use default and keyword arguments"]),
    (6,"Strings",["Apply string operations: indexing, slicing, concatenation","Use built-in string methods","Write programs to manipulate strings"]),
    (7,"Lists",["Create and modify lists","Apply list methods: append, insert, remove, sort","Write programs using list comprehension"]),
    (8,"Tuples and Dictionaries",["Distinguish tuples from lists","Create and access dictionary elements","Write programs using dictionaries"]),
]),

# ══ Grade 12 ══════════════════════════════════════════════════════════════════

(12,"XII","Physics","NCERT Physics Part I", 1,"Unit I – Electrostatics",[
    (1,"Electric Charges and Fields",["State Coulomb's law and apply it","Define electric field and draw field lines","Calculate field due to discrete and continuous charge distributions"]),
    (2,"Electrostatic Potential and Capacitance",["Define potential and potential difference","Calculate potential due to a point charge","Find capacitance and energy stored in a capacitor"]),
]),
(12,"XII","Physics","NCERT Physics Part I", 2,"Unit II – Current Electricity & Magnetism",[
    (3,"Current Electricity",["Apply Ohm's law and Kirchhoff's laws","Solve problems using Wheatstone bridge","Explain the EMF and internal resistance of a cell"]),
    (4,"Moving Charges and Magnetism",["Describe magnetic force on a current-carrying conductor","Derive Biot-Savart law for a circular loop","Explain torque on a current loop"]),
    (5,"Magnetism and Matter",["Classify materials as diamagnetic, paramagnetic, ferromagnetic","Define BH curve and hysteresis","Explain Earth's magnetism"]),
    (6,"Electromagnetic Induction",["State Faraday's laws of electromagnetic induction","Apply Lenz's law to determine direction of induced current","Derive expressions for self and mutual inductance"]),
    (7,"Alternating Current",["Derive phasor relations for R, L, C circuits","Define impedance and resonance","Calculate power in AC circuits"]),
    (8,"Electromagnetic Waves",["Describe Maxwell's equations qualitatively","Identify the electromagnetic spectrum","Explain properties of EM waves"]),
]),
(12,"XII","Physics","NCERT Physics Part II", 3,"Unit III – Optics",[
    (9,"Ray Optics and Optical Instruments",["Apply mirror and lens formulae","Derive the lens-maker's equation","Explain the working of microscope and telescope"]),
    (10,"Wave Optics",["State Huygens' principle","Explain Young's double-slit experiment","Describe diffraction and polarisation"]),
]),
(12,"XII","Physics","NCERT Physics Part II", 4,"Unit IV – Modern Physics",[
    (11,"Dual Nature of Radiation and Matter",["Explain the photoelectric effect","State de Broglie hypothesis","Calculate de Broglie wavelength"]),
    (12,"Atoms",["Describe Rutherford and Bohr models","Derive energy levels in hydrogen atom","Explain spectral series"]),
    (13,"Nuclei",["Define binding energy per nucleon","Explain radioactive decay laws","Describe nuclear fission and fusion"]),
    (14,"Semiconductor Electronics",["Distinguish between conductors, semiconductors and insulators","Describe p-n junction and its I-V characteristics","Explain rectifier, transistor and logic gates"]),
]),

(12,"XII","Chemistry","NCERT Chemistry Part I", 1,"Unit I – Solid State & Solutions",[
    (1,"The Solid State",["Classify solids based on bonding","Identify the types of unit cells","Calculate packing efficiency and density"]),
    (2,"Solutions",["Define concentration terms: molarity, molality, mole fraction","Apply Raoult's law","Explain colligative properties and their applications"]),
    (3,"Electrochemistry",["Define cell potential and relate it to Gibbs energy","Apply the Nernst equation","Calculate conductance and apply Kohlrausch's law"]),
    (4,"Chemical Kinetics",["Define rate of reaction and order","Integrate rate laws to find half-life","Apply Arrhenius equation to calculate activation energy"]),
]),
(12,"XII","Chemistry","NCERT Chemistry Part I", 2,"Unit II – p-Block & d-Block Elements",[
    (5,"Surface Chemistry",["Define adsorption and absorption","Describe types of colloids","Explain catalysis"]),
    (6,"General Principles and Processes of Isolation of Elements",["Explain the principles of metallurgy","Describe extraction of aluminium","Describe refining methods"]),
    (7,"The p-Block Elements",["Describe Group 15–18 elements","Explain properties and compounds of N, P, O, S, halogens, noble gases","Compare trends down the groups"]),
    (8,"The d- and f-Block Elements",["Describe characteristic properties of transition metals","Explain why transition metals show variable oxidation states","Describe lanthanoid and actinoid series"]),
    (9,"Coordination Compounds",["Define coordination entity and ligand","Apply IUPAC naming rules","Explain bonding using VBT and CFT"]),
]),
(12,"XII","Chemistry","NCERT Chemistry Part II", 3,"Unit III – Organic Chemistry",[
    (10,"Haloalkanes and Haloarenes",["Classify halogen compounds","Explain SN1 and SN2 mechanisms","Describe uses of halogenated compounds"]),
    (11,"Alcohols, Phenols and Ethers",["Classify and name alcohols, phenols and ethers","Describe preparation and reactions of each class","Compare acidic character of alcohols and phenols"]),
    (12,"Aldehydes, Ketones and Carboxylic Acids",["Describe nucleophilic addition to aldehydes and ketones","Compare acidic strength of carboxylic acids","Explain esterification"]),
    (13,"Amines",["Classify amines","Describe basicity of amines","Explain diazonium salt reactions"]),
    (14,"Biomolecules",["Classify carbohydrates and describe glucose","Describe the structure of proteins","Explain the double helix model of DNA"]),
    (15,"Polymers",["Classify polymers by source and structure","Describe condensation and addition polymerisation","Give examples of natural and synthetic polymers"]),
    (16,"Chemistry in Everyday Life",["Describe classes of drugs and their mechanisms","Explain cleansing action of soaps and detergents","Identify food additives and their roles"]),
]),

(12,"XII","Biology","NCERT Biology", 1,"Unit I – Reproduction",[
    (1,"Reproduction in Organisms",["Distinguish sexual from asexual reproduction","Describe modes of asexual reproduction","Explain the significance of reproductive events"]),
    (2,"Sexual Reproduction in Flowering Plants",["Describe the structure of the flower","Explain pollination and fertilisation","Describe development of seed and fruit"]),
    (3,"Human Reproduction",["Describe the male and female reproductive systems","Explain gametogenesis: spermatogenesis and oogenesis","Describe fertilisation and implantation"]),
    (4,"Reproductive Health",["Define reproductive health","Describe contraceptive methods","Explain problems of and solutions for infertility"]),
]),
(12,"XII","Biology","NCERT Biology", 2,"Unit II – Genetics & Evolution",[
    (5,"Principles of Inheritance and Variation",["State Mendel's laws of inheritance","Explain incomplete dominance and codominance","Describe sex-linked inheritance"]),
    (6,"Molecular Basis of Inheritance",["Describe DNA structure and replication","Explain the central dogma: transcription and translation","Describe regulation of gene expression"]),
    (7,"Evolution",["Explain the evidence for evolution","Describe Darwinian natural selection","Explain speciation and Hardy-Weinberg equilibrium"]),
]),
(12,"XII","Biology","NCERT Biology", 3,"Unit III – Biology in Human Welfare",[
    (8,"Human Health and Disease",["Classify diseases by cause","Describe immunity: innate, acquired, active, passive","Explain drug and alcohol abuse"]),
    (9,"Strategies for Enhancement in Food Production",["Describe plant breeding techniques","Explain single-cell protein and tissue culture","Describe animal husbandry practices"]),
    (10,"Microbes in Human Welfare",["Describe industrial uses of microbes","Explain microbes in sewage treatment","Describe microbes as biocontrol agents"]),
]),
(12,"XII","Biology","NCERT Biology", 4,"Unit IV – Biotechnology",[
    (11,"Biotechnology: Principles and Processes",["Explain recombinant DNA technology","Describe PCR and gel electrophoresis","Explain cloning vectors and bioreactors"]),
    (12,"Biotechnology and Its Applications",["Describe genetically modified organisms","Explain Bt crops and their safety concerns","Discuss biopiracy and related ethical issues"]),
]),
(12,"XII","Biology","NCERT Biology", 5,"Unit V – Ecology",[
    (13,"Organisms and Populations",["Define population and its characteristics","Explain interactions: predation, competition, mutualism","Apply logistic and exponential growth models"]),
    (14,"Ecosystem",["Describe the structure and functions of an ecosystem","Explain energy flow and ecological pyramids","Describe nutrient cycling: carbon and phosphorus"]),
    (15,"Biodiversity and Conservation",["Define biodiversity and its levels","Explain threats to biodiversity","Describe in-situ and ex-situ conservation"]),
    (16,"Environmental Issues",["Describe air, water and soil pollution","Explain deforestation and its effects","Discuss global warming and climate change"]),
]),

(12,"XII","Mathematics","NCERT Mathematics Part I", 1,"Unit I – Relations, Functions & Calculus",[
    (1,"Relations and Functions",["Distinguish types of relations","Identify types of functions: one-one, onto, bijective","Explain composition and inverse of functions"]),
    (2,"Inverse Trigonometric Functions",["Define inverse trig functions and their domains","Prove and apply properties of inverse trig functions","Simplify inverse trig expressions"]),
    (3,"Matrices",["Define matrix types and operations","Perform row operations on matrices","Find transpose and verify properties"]),
    (4,"Determinants",["Evaluate determinants of 2×2 and 3×3 matrices","Apply properties to simplify determinants","Find inverse using cofactor matrix"]),
]),
(12,"XII","Mathematics","NCERT Mathematics Part I", 2,"Unit II – Calculus",[
    (5,"Continuity and Differentiability",["Define continuity at a point and on an interval","Apply chain rule and differentiate implicit functions","Differentiate exponential and logarithmic functions"]),
    (6,"Application of Derivatives",["Find equations of tangent and normal","Apply increasing/decreasing function tests","Solve optimisation problems"]),
    (7,"Integrals",["Apply standard integrals and substitution","Use integration by parts","Evaluate definite integrals"]),
    (8,"Application of Integrals",["Find area bounded by curves and axes","Calculate area between two curves","Apply integration to real-life contexts"]),
    (9,"Differential Equations",["Form differential equations from families of curves","Solve variable separable equations","Solve homogeneous and linear differential equations"]),
]),
(12,"XII","Mathematics","NCERT Mathematics Part II", 3,"Unit III – Vectors & 3D Geometry",[
    (10,"Vector Algebra",["Define vector types and operations","Apply dot and cross products","Find area of parallelogram and triangle using vectors"]),
    (11,"Three Dimensional Geometry",["Find direction cosines and ratios","Derive equations of a line in 3D","Derive equations of a plane"]),
]),
(12,"XII","Mathematics","NCERT Mathematics Part II", 4,"Unit IV – Linear Programming & Probability",[
    (12,"Linear Programming",["Formulate an LPP from a word problem","Solve LPP graphically","Identify bounded and unbounded feasible regions"]),
    (13,"Probability",["Apply Bayes' theorem","Define and use random variables","Calculate mean and variance of a probability distribution"]),
]),

(12,"XII","History","Themes in Indian History", 1,"Unit I – Ancient & Medieval India",[
    (1,"Bricks, Beads and Bones: Harappan Civilisation",["Describe the urban planning of Harappan cities","Explain the economic activities of the Harappans","Discuss theories about the decline of the civilisation"]),
    (2,"Kings, Farmers and Towns",["Describe agrarian expansion in early India","Explain the emergence of cities after the Harappan period","Discuss coinage and trade"]),
    (3,"Kinship, Caste and Class",["Explain the varna system","Describe kinship practices in the Mahabharata","Discuss the emergence of caste"]),
    (4,"Thinkers, Beliefs and Buildings",["Describe the teachings of the Buddha and Mahavira","Explain the importance of stupas and temples","Discuss religious philosophy in ancient India"]),
]),
(12,"XII","History","Themes in Indian History", 2,"Unit II – Medieval India",[
    (5,"Through the Eyes of Travellers",["Identify major travellers to India","Describe what travellers observed about society and economy","Evaluate the reliability of travel accounts"]),
    (6,"Bhakti-Sufi Traditions",["Describe the Bhakti movement and its key figures","Explain Sufi orders and their teachings","Discuss the impact on society"]),
    (7,"An Imperial Capital: Vijayanagara",["Describe the layout of Vijayanagara city","Explain the significance of the Mahanavami dibba","Discuss the decline of the empire"]),
    (8,"Peasants, Zamindars and the State",["Describe the agrarian system under the Mughals","Explain the role of zamindars","Discuss peasant revolts"]),
]),
(12,"XII","History","Themes in Indian History", 3,"Unit III – Colonial India & Constitution",[
    (9,"Colonialism and the Countryside",["Explain the Permanent Settlement","Describe the condition of peasants under colonial rule","Discuss the Deccan riots"]),
    (10,"Rebels and the Raj",["Describe the causes of the revolt of 1857","Identify major centres and leaders of the revolt","Discuss the aftermath"]),
    (11,"Mahatma Gandhi and the Nationalist Movement",["Describe Gandhi's early life and return to India","Explain the major movements led by Gandhi","Discuss the partition of India"]),
    (12,"Understanding Partition",["Explain the events leading to partition","Describe its human cost","Discuss different perspectives on partition"]),
    (13,"Framing the Constitution",["Describe the working of the Constituent Assembly","Explain the key features of the Indian Constitution","Discuss debates in the Constituent Assembly"]),
]),

(12,"XII","Computer Science","NCERT Computer Science", 1,"Unit I – Python Advanced",[
    (1,"Exception Handling",["Define exceptions and their types","Handle exceptions using try-except-finally","Raise user-defined exceptions"]),
    (2,"File Handling",["Open, read, write and close text and binary files","Use pickle for binary file operations","Handle file-related exceptions"]),
]),
(12,"XII","Computer Science","NCERT Computer Science", 2,"Unit II – Data Structures",[
    (3,"Stack",["Define stack and its LIFO property","Implement a stack in Python","Apply stacks to balance parentheses and evaluate expressions"]),
    (4,"Queue",["Define queue and its FIFO property","Implement a simple and circular queue","Differentiate between queue and deque"]),
    (5,"Searching and Sorting",["Implement linear and binary search","Apply bubble, insertion and selection sort","Analyse time complexity of each algorithm"]),
]),
(12,"XII","Computer Science","NCERT Computer Science", 3,"Unit III – Databases & Networking",[
    (6,"Database Concepts",["Define DBMS and its advantages","Describe the relational model: tables, keys, relations","Explain entity-relationship model"]),
    (7,"Structured Query Language",["Write DDL commands: CREATE, ALTER, DROP","Write DML commands: SELECT, INSERT, UPDATE, DELETE","Apply aggregate functions and JOIN operations"]),
    (8,"Computer Networks",["Describe network types: LAN, WAN, MAN","Explain TCP/IP and OSI models","Describe network devices: hub, switch, router"]),
    (9,"Societal Impacts",["Identify cyber threats and preventive measures","Explain digital footprint and privacy","Discuss e-waste management and ethics"]),
]),
]  # end CBSE_DATA

# ─────────────────────────────────────────────────────────────────────────────
# ICSE (Grades 1–10)  — key subjects with unit/chapter structure
# ─────────────────────────────────────────────────────────────────────────────

ICSE_DATA = [
(10,"10","Mathematics","ICSE Mathematics", 1,"Unit I – Commercial Mathematics",[
    (1,"GST – Goods and Services Tax",["Define GST and its components: CGST, SGST, IGST","Calculate GST for various goods and services","Solve problems involving input tax credit"]),
    (2,"Banking",["Define recurring and fixed deposit accounts","Calculate maturity value of RD and FD","Solve problems on banking using given interest rates"]),
    (3,"Shares and Dividends",["Define shares, dividends and stock market terms","Calculate dividend yield","Find number of shares that can be purchased with a given investment"]),
]),
(10,"10","Mathematics","ICSE Mathematics", 2,"Unit II – Algebra",[
    (4,"Linear Inequations",["Define linear inequation and solution set","Represent solution on a number line","Solve word problems involving inequations"]),
    (5,"Quadratic Equations",["Solve quadratic equations by factorisation and formula","Find the discriminant and determine nature of roots","Solve application problems"]),
    (6,"Ratio and Proportion",["Apply componendo-dividendo","Solve problems involving continued proportion","Apply proportion to real-life situations"]),
    (7,"Factorisation",["Factorise expressions using standard identities","Use the factor theorem","Divide a polynomial by a linear factor"]),
]),
(10,"10","Mathematics","ICSE Mathematics", 3,"Unit III – Geometry",[
    (8,"Similarity",["State and apply similarity criteria: AA, SAS, SSS","Solve problems involving similar triangles","Apply similarity to maps and models"]),
    (9,"Locus",["Define locus","Construct standard loci","Solve intersection of loci problems"]),
    (10,"Circles",["Apply the angle-in-alternate-segment theorem","Prove the tangent-chord angle","Solve problems involving angles in a circle"]),
    (11,"Constructions",["Construct circumscribed and inscribed circles of a triangle","Divide a segment in a given ratio","Construct a triangle similar to a given triangle"]),
]),
(10,"10","Physics","ICSE Physics", 1,"Unit I – Force, Work and Energy",[
    (1,"Force",["Define moment of force and couple","Apply the principle of moments","Solve problems involving levers and equilibrium"]),
    (2,"Work, Energy and Power",["Calculate work done by a force","Apply the work-energy theorem","Distinguish between different forms of mechanical energy"]),
    (3,"Machines",["Classify simple machines","Define mechanical advantage, velocity ratio and efficiency","Solve problems on pulleys and inclined planes"]),
]),
(10,"10","Physics","ICSE Physics", 2,"Unit II – Light & Sound",[
    (4,"Refraction of Light at Plane Surfaces",["Apply Snell's law of refraction","Explain total internal reflection","Calculate critical angle"]),
    (5,"Refraction Through Lens",["Derive the thin lens formula","Calculate magnification","Solve problems involving concave and convex lenses"]),
    (6,"Spectrum",["Describe dispersion of white light","Explain the electromagnetic spectrum","Describe the recombination of colours"]),
    (7,"Sound",["Describe the nature of sound","Explain resonance and echo","Solve numerical problems on echo"]),
]),
(10,"10","Chemistry","ICSE Chemistry", 1,"Unit I – Periodic Properties & Bonding",[
    (1,"Periodic Properties and Variations of Properties",["Describe periodic trends: atomic radius, ionisation energy, electronegativity","Compare properties across periods and down groups","Predict properties of elements based on their position"]),
    (2,"Chemical Bonding",["Define and distinguish ionic and covalent bonds","Draw electron dot structures","Explain electrovalency and covalency"]),
]),
(10,"10","Chemistry","ICSE Chemistry", 2,"Unit II – Chemical Reactions",[
    (3,"Acids Bases and Salts",["Define Arrhenius and Brønsted-Lowry acids and bases","Describe preparation of salts by neutralisation and double decomposition","Identify acidic, basic and neutral salts"]),
    (4,"Electrolysis",["Define electrolysis and electrolyte","Identify products of electrolysis of various solutions","State Faraday's laws of electrolysis"]),
    (5,"Metallurgy",["Describe the extraction of aluminium from bauxite","Explain the extraction of iron in a blast furnace","Describe refining of metals"]),
    (6,"Organic Chemistry",["Define organic compounds and functional groups","Name and draw structures of alkanes, alkenes and alkynes","Describe preparation and properties of ethanol and ethanoic acid"]),
]),
(10,"10","Biology","ICSE Biology", 1,"Unit I – Cell Biology",[
    (1,"Cell Division",["Describe the stages of mitosis and meiosis","Compare mitosis and meiosis","Explain the significance of each type"]),
    (2,"Genetics",["Define gene, chromosome and allele","Apply Mendel's laws to genetic crosses","Explain sex-linked inheritance"]),
]),
(10,"10","Biology","ICSE Biology", 2,"Unit II – Plant Physiology",[
    (3,"Absorption by Roots",["Describe osmosis and its role in water absorption","Explain root pressure and transpiration pull","Describe the path of water from roots to leaves"]),
    (4,"Transpiration",["Define transpiration and guttation","Describe the factors affecting transpiration","Explain the significance of transpiration"]),
    (5,"Photosynthesis",["Write the overall equation of photosynthesis","Describe the light-dependent and light-independent reactions","Explain factors affecting the rate of photosynthesis"]),
]),
(10,"10","Biology","ICSE Biology", 3,"Unit III – Human Physiology",[
    (6,"The Circulatory System",["Describe the structure of the human heart","Explain the cardiac cycle","Describe blood groups and their significance"]),
    (7,"The Excretory System",["Describe the structure of the kidney","Explain urine formation: filtration, reabsorption and secretion","Describe dialysis"]),
    (8,"The Nervous System",["Describe the structure of a neuron","Explain reflex action","Describe the structure and functions of the brain"]),
    (9,"The Endocrine System",["Name major endocrine glands and their hormones","Explain feedback mechanisms","Describe disorders caused by hormonal imbalance"]),
]),
(10,"10","History & Civics","ICSE History & Civics", 1,"Unit I – Civics",[
    (1,"The Union Parliament",["Describe the composition of Lok Sabha and Rajya Sabha","Explain the legislative process","Describe the powers and functions of Parliament"]),
    (2,"The Executive",["Describe the role of the President and Vice-President","Explain the Cabinet system","Describe the role of the Prime Minister"]),
    (3,"The Judiciary",["Describe the structure of the Indian judicial system","Explain original and appellate jurisdiction of the Supreme Court","Describe the High Courts and subordinate courts"]),
]),
(10,"10","History & Civics","ICSE History & Civics", 2,"Unit II – History",[
    (4,"Rise of Nationalism in Europe",["Explain Metternich's Europe","Describe the unification of Italy and Germany","Discuss the impact of nationalism on European politics"]),
    (5,"Nationalism in India: Phase I",["Describe the formation of the Indian National Congress","Explain the Swadeshi Movement","Describe the partition of Bengal"]),
    (6,"Nationalism in India: Phase II & III",["Describe the Non-Cooperation Movement","Explain the Civil Disobedience Movement","Describe the Quit India Movement"]),
]),
]  # end ICSE_DATA

# ─────────────────────────────────────────────────────────────────────────────
# ISC (Grades 11–12)
# ─────────────────────────────────────────────────────────────────────────────

ISC_DATA = [
(12,"XII","Computer Science","ISC Computer Science", 1,"Unit I – OOP in Java",[
    (1,"Objects and Classes",["Define class, object, constructor","Implement data hiding and encapsulation","Use access specifiers: public, private, protected"]),
    (2,"Inheritance and Polymorphism",["Implement single and multilevel inheritance","Override methods","Apply run-time polymorphism using dynamic binding"]),
    (3,"Interfaces and Packages",["Define and implement interfaces","Describe the use of packages","Apply the abstract class concept"]),
]),
(12,"XII","Computer Science","ISC Computer Science", 2,"Unit II – Data Structures",[
    (4,"Linked Lists",["Define singly and doubly linked lists","Insert and delete nodes","Traverse a linked list"]),
    (5,"Stacks and Queues",["Implement stack and queue using arrays and linked lists","Evaluate infix and postfix expressions","Simulate a queue for scheduling"]),
    (6,"Binary Trees",["Define binary tree and its properties","Implement traversal: inorder, preorder, postorder","Describe binary search tree operations"]),
]),
(12,"XII","Computer Science","ISC Computer Science", 3,"Unit III – Networking & DBMS",[
    (7,"Networking",["Describe types of networks","Explain protocols: TCP/IP, HTTP, FTP","Identify network devices and their functions"]),
    (8,"Database Management",["Define RDBMS concepts","Write SQL queries using DML and DDL","Apply normalisation: 1NF, 2NF, 3NF"]),
]),
(12,"XII","Mathematics","ISC Mathematics", 1,"Unit I – Algebra & Trigonometry",[
    (1,"Boolean Algebra",["Define Boolean variables and operations","Simplify Boolean expressions","Construct and verify truth tables"]),
    (2,"Conics",["Derive standard equations of parabola, ellipse, hyperbola","Find focus, directrix and eccentricity","Solve problems on conics"]),
    (3,"Inverse Trigonometric Functions",["Define inverse trigonometric functions","Prove standard identities","Solve inverse trig equations"]),
]),
(12,"XII","Mathematics","ISC Mathematics", 2,"Unit II – Calculus",[
    (4,"Differential Calculus",["Differentiate implicit and parametric functions","Apply L'Hôpital's rule","Find maxima, minima and points of inflection"]),
    (5,"Integral Calculus",["Evaluate integrals using partial fractions","Apply integration by parts repeatedly","Solve definite integrals using properties"]),
    (6,"Differential Equations",["Form and solve separable differential equations","Solve homogeneous ODEs","Solve linear first-order ODEs using integrating factor"]),
]),
(12,"XII","Mathematics","ISC Mathematics", 3,"Unit III – Statistics & Probability",[
    (7,"Probability",["Apply Bayes' theorem","Define random variable and probability distribution","Calculate expectation and variance"]),
    (8,"Linear Programming",["Formulate and solve LPP graphically","Identify feasible region and optimal solution","Apply LPP to transportation and assignment problems"]),
]),
]  # end ISC_DATA

# ─────────────────────────────────────────────────────────────────────────────
# Maharashtra State Board (Grades 9-12 focus with realistic units)
# ─────────────────────────────────────────────────────────────────────────────

MH_DATA = [
(10,"10","Mathematics","Maharashtra SSC Mathematics", 1,"Unit I – Algebra",[
    (1,"Linear Equations in Two Variables",["Solve simultaneous equations by substitution, elimination and graphical methods","Form and solve word problems","Apply Cramer's rule"]),
    (2,"Quadratic Equations",["Solve by factorisation and completing the square","Apply the quadratic formula","Solve word problems: numbers, areas, time-speed"]),
    (3,"Arithmetic Progression",["Find nth term and sum of AP","Apply AP to real-life problems","Determine whether a sequence is an AP"]),
]),
(10,"10","Mathematics","Maharashtra SSC Mathematics", 2,"Unit II – Geometry",[
    (4,"Similarity",["State criteria for similarity","Solve problems using Basic Proportionality Theorem","Apply similarity to practical situations"]),
    (5,"Circle",["Prove tangent-radius perpendicularity","Apply the angle in alternate segment theorem","Solve problems on tangents"]),
    (6,"Co-ordinate Geometry",["Apply distance formula","Use section formula","Find area of a triangle given vertices"]),
    (7,"Trigonometry",["Apply trigonometric ratios to heights and distances","Prove trigonometric identities","Solve problems involving angle of elevation and depression"]),
]),
(10,"10","Science I","Maharashtra SSC Science I", 1,"Unit I – Chemical Reactions & Compounds",[
    (1,"Chemical Reactions and Equations",["Balance chemical equations","Classify reactions","Identify oxidation and reduction in reactions"]),
    (2,"Acids, Bases and Salts",["Describe properties of acids, bases and salts","Explain indicators and pH","Describe preparation of salts"]),
    (3,"Metal and Non-metals",["Describe physical and chemical properties","Explain reactivity series","Describe corrosion and prevention"]),
]),
(10,"10","Science II","Maharashtra SSC Science II", 1,"Unit I – Life Processes",[
    (1,"Life Processes",["Describe nutrition and digestion in humans","Explain human respiratory and circulatory systems","Describe excretion in humans"]),
    (2,"Control and Coordination",["Describe the human nervous system","Explain reflex arc","Name endocrine glands and their hormones"]),
    (3,"Reproduction",["Describe sexual and asexual reproduction in plants","Describe human reproduction","Explain reproductive health"]),
]),
(12,"XII","Physics","Maharashtra HSC Physics", 1,"Unit I – Circular & Rotational Motion",[
    (1,"Circular Motion",["Define angular displacement, velocity and acceleration","Derive centripetal acceleration","Solve banking of road problems"]),
    (2,"Rotational Motion",["Define torque and moment of inertia","Apply the theorem of parallel and perpendicular axes","Derive expression for rotational kinetic energy"]),
    (3,"Oscillations",["Derive equations for SHM","Find time period of simple pendulum","Explain energy in SHM"]),
]),
(12,"XII","Chemistry","Maharashtra HSC Chemistry", 1,"Unit I – Solid State & Solutions",[
    (1,"Solid State",["Describe crystal lattice types","Calculate packing efficiency","Explain point defects"]),
    (2,"Solutions and Colligative Properties",["Define concentration units","Explain colligative properties","Apply van't Hoff factor"]),
    (3,"Chemical Thermodynamics",["Define enthalpy and entropy","Apply Hess's law","Calculate Gibbs energy and predict spontaneity"]),
]),
(12,"XII","Biology","Maharashtra HSC Biology", 1,"Unit I – Genetics & Evolution",[
    (1,"Genetics and Molecular Basis of Inheritance",["Describe DNA replication","Explain transcription and translation","Explain lac operon"]),
    (2,"Biotechnology and Its Applications",["Define recombinant DNA technology","Explain PCR and gel electrophoresis","Describe applications: GMOs, gene therapy"]),
    (3,"Evolution",["Describe evidence for evolution","Explain Hardy-Weinberg law","Discuss mechanisms of speciation"]),
]),
(12,"XII","Mathematics","Maharashtra HSC Mathematics", 1,"Unit I – Mathematical Logic",[
    (1,"Mathematical Logic",["Define statements and logical connectives","Construct truth tables","Prove logical equivalences"]),
    (2,"Matrices",["Perform matrix operations","Find inverse using elementary row operations","Apply matrices to solve a system of equations"]),
    (3,"Trigonometric Functions",["Prove compound angle formulae","Apply product-to-sum and sum-to-product formulae","Solve trigonometric equations"]),
]),
]  # end MH_DATA

# ─────────────────────────────────────────────────────────────────────────────
# Karnataka State Board (Grades 9-12)
# ─────────────────────────────────────────────────────────────────────────────

KA_DATA = [
(10,"10","Mathematics","Karnataka SSLC Mathematics", 1,"Unit I – Arithmetic",[
    (1,"Real Numbers",["Prove irrationality of surds","Apply Euclid's division lemma","State the fundamental theorem of arithmetic"]),
    (2,"Polynomials",["Find zeros of quadratic polynomials","Verify sum and product of zeros","Perform polynomial division"]),
]),
(10,"10","Mathematics","Karnataka SSLC Mathematics", 2,"Unit II – Algebra & Geometry",[
    (3,"Pair of Linear Equations",["Solve graphically and algebraically","Classify as consistent or inconsistent","Solve word problems"]),
    (4,"Quadratic Equations",["Solve by factorisation and formula","Determine nature of roots","Solve application problems"]),
    (5,"Triangles",["Apply BPT and converse","State AA, SAS and SSS similarity criteria","Apply Pythagoras' theorem"]),
]),
(10,"10","Science","Karnataka SSLC Science", 1,"Unit I – Chemical Substances",[
    (1,"Chemical Reactions and Equations",["Write and balance chemical equations","Classify reaction types","Identify redox reactions"]),
    (2,"Acids, Bases and Salts",["Describe properties of acids and bases","Explain pH scale","Describe preparation of common salts"]),
]),
(10,"10","Science","Karnataka SSLC Science", 2,"Unit II – Physics",[
    (3,"Light: Reflection and Refraction",["Apply mirror formula","Apply Snell's law and lens formula","Describe power of a lens"]),
    (4,"Electricity",["Apply Ohm's law","Calculate resistance in series and parallel","Apply Joule's heating law"]),
    (5,"Magnetic Effects of Current",["Describe Fleming's left-hand rule","Explain electromagnetic induction","Describe AC and DC generators"]),
]),
(12,"XII","Physics","Karnataka PU Physics", 1,"Unit I – Electrostatics",[
    (1,"Electric Charges and Fields",["Apply Coulomb's law","Draw electric field lines","Find electric field due to dipole"]),
    (2,"Electrostatic Potential and Capacitance",["Define potential energy of a system of charges","Derive expression for capacitance","Find energy stored in a capacitor"]),
    (3,"Current Electricity",["Apply Kirchhoff's laws","Use Wheatstone bridge","Explain drift velocity and mobility"]),
]),
(12,"XII","Chemistry","Karnataka PU Chemistry", 1,"Unit I – Solid State & Electrochemistry",[
    (1,"Solid State",["Describe crystal systems","Calculate density from unit cell parameters","Explain electrical properties"]),
    (2,"Electrochemistry",["Describe galvanic cells","Apply Nernst equation","Explain electrolysis and Faraday's laws"]),
]),
(12,"XII","Mathematics","Karnataka PU Mathematics", 1,"Unit I – Relations & Calculus",[
    (1,"Relations and Functions",["Define and classify relations","Identify types of functions","Find composition and inverse"]),
    (2,"Inverse Trigonometric Functions",["Find domain and range of inverse trig functions","Simplify inverse trig expressions","Solve inverse trig equations"]),
    (3,"Matrices and Determinants",["Perform matrix operations","Find inverse of a matrix","Solve system of equations using Cramer's rule"]),
]),
]  # end KA_DATA

# ─────────────────────────────────────────────────────────────────────────────
# Tamil Nadu Samacheer Kalvi (Grades 9-12)
# ─────────────────────────────────────────────────────────────────────────────

TN_DATA = [
(10,"10","Mathematics","TN Samacheer Kalvi Mathematics", 1,"Unit I – Numbers & Algebra",[
    (1,"Relations and Functions",["Define relation and function","Identify domain range and codomain","Classify functions by type"]),
    (2,"Numbers and Sequences",["Apply Euclid's division algorithm","Find HCF and LCM","Identify AP and GP sequences"]),
    (3,"Algebra",["Solve quadratic equations","Apply Vieta's formulae","Find GCD of polynomials"]),
]),
(10,"10","Mathematics","TN Samacheer Kalvi Mathematics", 2,"Unit II – Geometry & Trigonometry",[
    (4,"Geometry",["Apply Basic Proportionality Theorem","Use Pythagoras and converse","Apply tangent-chord angle"]),
    (5,"Coordinate Geometry",["Apply distance and section formulae","Find area of triangle from coordinates","Derive equation of a line"]),
    (6,"Trigonometry",["Apply compound angle formulae","Use height and distance problems","Prove trigonometric identities"]),
]),
(10,"10","Science","TN Samacheer Kalvi Science", 1,"Unit I – Physics",[
    (1,"Laws of Motion",["Apply Newton's laws","Define momentum and impulse","Explain uniform circular motion"]),
    (2,"Optics",["Describe reflection at plane and curved mirrors","Apply Snell's law","Explain lenses and optical instruments"]),
    (3,"Electricity",["Define EMF and internal resistance","Apply Kirchhoff's laws","Explain domestic electric circuits"]),
]),
(10,"10","Science","TN Samacheer Kalvi Science", 2,"Unit II – Biology",[
    (4,"Plant Physiology",["Describe transport in plants","Explain photosynthesis and factors","Describe transpiration pull"]),
    (5,"Nervous System",["Describe the human nervous system","Explain reflex arc","Describe the brain structure"]),
    (6,"Reproduction and Genetics",["Describe sexual reproduction in plants","Explain DNA structure and replication","Apply Mendel's laws"]),
]),
(12,"XII","Physics","TN Samacheer Kalvi Physics", 1,"Unit I – Electrostatics & Current",[
    (1,"Electrostatics",["Apply Gauss's law","Find potential due to various charge distributions","Explain dielectrics and capacitance"]),
    (2,"Current Electricity",["Apply Kirchhoff's laws","Explain drift velocity and resistivity","Describe thermoelectric effects"]),
    (3,"Magnetism and Magnetic Effects",["Describe the magnetic field due to various configurations","Apply Ampere's circuital law","Explain electromagnetic induction"]),
]),
(12,"XII","Chemistry","TN Samacheer Kalvi Chemistry", 1,"Unit I – Atomic Structure & Bonding",[
    (1,"Atomic Structure",["Explain the quantum mechanical model","Write electronic configurations","Describe quantum numbers"]),
    (2,"Periodic Classification",["Describe periodic trends","Explain anomalous properties","Predict element properties from position"]),
    (3,"Chemical Bonding",["Describe covalent bonding using MOT","Apply VSEPR to predict structure","Explain hybridisation"]),
]),
(12,"XII","Mathematics","TN Samacheer Kalvi Mathematics", 1,"Unit I – Matrices & Complex Numbers",[
    (1,"Applications of Matrices and Determinants",["Apply Cayley-Hamilton theorem","Find rank of a matrix","Solve non-homogeneous systems"]),
    (2,"Complex Numbers",["Represent complex numbers geometrically","Apply De Moivre's theorem","Find roots of a complex number"]),
    (3,"Theory of Equations",["Apply the fundamental theorem of algebra","Use Descartes' rule of signs","Find roots by numerical methods"]),
]),
(12,"XII","Biology","TN Samacheer Kalvi Biology", 1,"Unit I – Genetics & Biotechnology",[
    (1,"Principles of Inheritance",["Explain Mendelian inheritance","Describe sex-linked inheritance","Explain chromosomal theory"]),
    (2,"Molecular Genetics",["Describe DNA structure and replication","Explain transcription in prokaryotes","Explain translation and the genetic code"]),
    (3,"Biotechnology",["Explain recombinant DNA technology","Describe PCR applications","Discuss bioethics in biotechnology"]),
]),
]  # end TN_DATA

# ─────────────────────────────────────────────────────────────────────────────
# Row builder
# ─────────────────────────────────────────────────────────────────────────────

def build_rows(data, group_id):
    rows = []
    src_cache = {}
    for entry in data:
        grade, grade_code, subject, textbook, unit_no, unit_title, lessons = entry
        src_key = (subject, grade)
        if src_key not in src_cache:
            src_cache[src_key] = _uid()
        src_id = src_cache[src_key]

        for lesson_no, lesson_title, objectives in lessons:
            rows.append(make_row(
                group_id, src_id, grade, grade_code, subject, textbook,
                unit_no, unit_title, lesson_no, lesson_title, objectives,
            ))
    return rows

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

BOARD_DATA = {
    "CBSE":     CBSE_DATA,
    "ICSE":     ICSE_DATA,
    "ISC":      ISC_DATA,
    "MH_STATE": MH_DATA,
    "KA_STATE": KA_DATA,
    "TN_STATE": TN_DATA,
}

def main():
    load_supabase_env_from_registry()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        print("ERROR: set SUPABASE_URL and SUPABASE_KEY env vars")
        sys.exit(1)

    sb = create_client(url, key)
    print("Connected to Supabase.\n")

    total = 0
    for board in BOARDS:
        code = board["code"]
        print(f"\n=== {code} — {board['name']} ===")
        gid = _upsert_group(sb, board)
        data = BOARD_DATA.get(code, [])
        if not data:
            print(f"  (no data defined for {code})")
            continue
        rows = build_rows(data, gid)
        saved = _batch_insert(sb, rows)
        total += saved
        print(f"  inserted {saved} / {len(rows)} items")

    print(f"\n✓ Done. Total rows inserted: {total}")

if __name__ == "__main__":
    main()
