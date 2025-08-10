import random
from faker import Faker

fake = Faker()

# Configuration
num_events = 300
num_persons = 300

# Generate Event INSERTs
event_inserts = []
for _ in range(num_events):
    subject = fake.sentence(nb_words=6).replace("'", "''")
    date = fake.date_between(start_date='-2y', end_date='today')
    source = fake.company().replace("'", "''")[:50]
    latitude = round(fake.latitude(), 6)
    longitude = round(fake.longitude(), 6)
    address = fake.address().replace("'", "''").replace("\n", ", ")
    description = fake.text(max_nb_chars=500).replace("'", "''")
    query = f"INSERT INTO [dbo].[Event] (Subject, Date, Source, Latitude, Longitude, Address, Description) VALUES ('{subject}', '{date}', '{source}', {latitude}, {longitude}, '{address}', '{description}');"
    event_inserts.append(query)

# Generate Person INSERTs
person_inserts = []
for _ in range(num_persons):
    name = fake.name().replace("'", "''")
    ssn = fake.ssn()
    biodata = fake.text(max_nb_chars=500).replace("'", "''")
    education = fake.text(max_nb_chars=300).replace("'", "''")
    work = fake.text(max_nb_chars=300).replace("'", "''")
    query = f"INSERT INTO [dbo].[Person] (Name, SSN, BioData, Education, Work) VALUES ('{name}', '{ssn}', '{biodata}', '{education}', '{work}');"
    person_inserts.append(query)

# Generate EventPerson INSERTs (ensuring each Event has multiple persons)
event_person_inserts = set()  # use a set to avoid duplicates

for event_id in range(1, num_events + 1):
    num_links = random.randint(1, 5)  # each event linked to 1–5 people
    person_ids = random.sample(range(1, num_persons + 1), num_links)
    for person_id in person_ids:
        event_person_inserts.add((event_id, person_id))

# Create SQL INSERT statements for EventPerson
event_person_queries = [
    f"INSERT INTO [dbo].[EventPerson] (EventId, PersonId) VALUES ({event_id}, {person_id});"
    for (event_id, person_id) in event_person_inserts
]

# Combine and shuffle all queries
all_inserts = event_inserts + person_inserts + event_person_queries
random.shuffle(all_inserts)

# Select up to 1000 queries
output_queries = all_inserts[:1000]

# Save to file (optional)
with open("insert_queries.sql", "w") as f:
    for query in output_queries:
        f.write(query + "\n")

print(f"Generated {len(output_queries)} SQL INSERT queries and saved to insert_queries.sql")
