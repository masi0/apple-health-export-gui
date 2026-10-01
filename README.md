I was looking for an app that takes specific Health data and wrap it into a markdown file so I can use it with AI for analysis.
I failed, so I have decided to write my own app that does that.

How to use it?

1. Open Health app on iOS
2. click your profile icon and scroll down
3. click "Export all health data"
4. once data is generated save it into accessible location (on your Mac)
5. extract zip file into the folder
6. there is export.xml file in that folder
7. run python3 apple_health_gui.py
8. select that XML file location
9. specific markdown file location
10. select data range*, metrics and type of workouts

    *you need to know your dates range
