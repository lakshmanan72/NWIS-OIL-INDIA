import fitz

# 1. Create real_wcr_nhk_542.pdf
doc1 = fitz.open()
page1 = doc1.new_page()
text1 = """OIL INDIA LIMITED
WELL COMPLETION REPORT (WCR)
DIRECTORATE OF DRILLING & WELL SERVICES - DULIAJAN, ASSAM

WELL IDENTIFICATION & SUMMARY
Well Name: NHK-542
Operator: Oil India Limited
Field: Nahorkatiya
Basin: Assam-Arakan
Block: Dibrugarh Onshore OALP-I
Well Type: Development
Trajectory: Vertical
Well Status: Producing

SURFACE LOCATION & GEOGRAPHIC COORDINATES
Surface Coordinates:
Latitude: 27° 18' 42.6" N
Longitude: 95° 21' 14.8" E
Elevation Ground Level: 118.5 m MSL

OPERATIONAL TIMELINE & DEPTH
Spud Date: 2024-02-10
Completion Date: 2024-05-18
Total Depth: 3450 m
Target Formation: Barail Sandstone

HISTORICAL DRILLING & WELLBORE EVENTS
1. Depth 1820m: Severe Mud Loss encountered in Tipam Formation. 45 bbls of synthetic fluid lost to formation. LCM pill spotted.
2. Depth 2650m: Stuck Pipe incident while pulling out of hole in Barail Coal-Shale section. Free point determined, pipe freed after 14 hours.
3. Depth 3150m: Pressure Issue - unexpected 400 psi gas kick recorded in upper Barail sands. Well killed successfully with 11.2 ppg mud.
"""
page1.insert_text(fitz.Point(50, 50), text1, fontsize=11)
doc1.save("real_wcr_nhk_542.pdf")
doc1.close()

# 2. Create wcr_no_coords_demo.pdf (Zero hallucination test)
doc2 = fitz.open()
page2 = doc2.new_page()
text2 = """OIL INDIA LIMITED
WELL COMPLETION REPORT (WCR)
TECHNICAL DRILLING REPORT

WELL SUMMARY
Well Name: BOGAPANI-DEEP-09
Operator: Oil India Limited
Field: Bogapani
Basin: Assam Shelf
Block: AAP-ON-94/1
Well Type: Exploration
Well Status: Suspended

OPERATIONAL DETAILS
Spud Date: 2023-11-01
Completion Date: 2024-01-20
Total Depth: 4120 m
Primary Formation: Kopili Shale

Note: Surface geographic coordinates survey pending formal DGMS / DGH clearance.
Surveyor report to be annexed in final revision.

OPERATIONAL EVENTS
1. Depth 2400m: Mud Loss 20 bbls in Girujan Clay.
"""
page2.insert_text(fitz.Point(50, 50), text2, fontsize=11)
doc2.save("wcr_no_coords_demo.pdf")
doc2.close()

print("Successfully generated real_wcr_nhk_542.pdf and wcr_no_coords_demo.pdf")
