## OpenFarmer

> This script is based on https://github.com/lintan/OpenFarmer, the manual and code translated to english, plan to add some features on the basis of his feature, thanks to this big selfless dedication.

### A free, open source farmer world farmersworld hang-up script

Visual interface

![Image](https://raw.githubusercontent.com/bitlegger/OpenFarmer/main/doc/demo-gui1.png)
![Image](https://raw.githubusercontent.com/bitlegger/OpenFarmer/main/doc/demo-gui2.png)

Command line interface legend:

![Image](https://raw.githubusercontent.com/bitlegger/OpenFarmer/main/doc/demo-main1.png)

### Original intention

The popularity of Farmersworld https://farmersworld.io is believed to be obvious to all.

Various auxiliary scripts on the Internet are also flying all over the sky, but the large-scale hacking incident carried out by a script company on November 7, 2021 made the majority of farmers sad and angry.

So I decided to open a simple hang-up script that I wrote, there is no gorgeous interface, only simple profiles and command lines, although it is not good, but absolutely peaceful

The code is fully open, excluding any binary executable, does not include any back door virus, completely deserving inspection

At the same time, you are welcome to mention bugs and push code, constantly improve it.

This project uses Python3 + Selenium development

Expans the platform, support Windows, Linux, MacOS


### Features

1. Support a computer on a computer
2. Support to set up HTTP proxy
3. Support all tools under Mining (ax, stone ax, saw, fishing rod, fishing net, fishing boat, excavator, etc.)
4. Support all crops (barley, corn) under Plant, automatic planting
5. Support Eggs -> Chick -> Chicken Automatic Feeding
6. Support the calf -> Cattle -> Dairy feeding
7. Support membership card automatic click
8. Tool durable automatic repair (please prepare enough gold coins)
9. Energy is insufficient automatically (please have enough meat)
10. Support automatic construction (new number for the first time COOP and FARM PLOT requires 8 operations)
11. Support eggs, milk, barley, maize automatic sale
12. Support food, gold insufficient automatic recharge
13. Automatic speed when supporting 5% ratio


### Use

Suspected students can download the latest packaged version directly on the [Releases] on the right side of the GitHub page, which only supports the Windows 64-bit system. It is recommended to run on the Win10 system, extract the directory in the compressed package, double-click to run [Gui.exe] You can, the command line version can run [main.exe], need to manually modify the configuration file before using the command line version [user.yml]

There is a requirement for security, like the drum code, it is recommended to run from the source code, step by step according to the following steps.

### Use
1. Click [CODE] => gitclone source to the local, or Download Zip Download Source Code to Local
2. Download and install Python3 (version must be greater than equals Python3.7)
   
   Please download the latest version to Python official website:
   https://www.python.org/downloads/
   
   [Note] Please remember to check [Add Python 3.10 to Path]
3. Double-click to run [Install_Depends.py] to install the dependencies, one computer only needs to install it once
   [Note] Please turn off the wall agent before installing and dependent, turn off the scientific Internet, otherwise you can't download the dependent package from Douban PYPI Mirror Station.
4. Install the Chrome browser and upgrade to the latest version (in the current version, make sure that the Chromedriver version is consistent)
5. Download Chromedriver, version to ensure that the Chrome version is consistent
https://chromedriver.chromium.org/downloads

For example, my Chrome version is 97.0.4664.45

    Then I will download Chromedriver 97.0.4664.45

    In fact, the small version is inconsistent, it doesn't matter, the big version number 97 is consistent
   
   Windows system Download [chromedriver_win32.zip]
6. Differently extract the chromedriver.exe file in the downloaded Chromedriver compression package into the source directory of this item (and main.py in a directory)
7. Modify the configuration file [user.yml]
   1. Copy a user.yml.example file, renamedered User.yml
   2. Set the various parameters according to your actual situation (Modify User.yml recommended using the NodePad ++ editor, download link: [Click to download NodePad ++ Editor] (https://github.com/notepad-plus-plus/notepad-plus- Plus / Releases / Download / V8.2 / NPP.8.2.Installer.x64.exe))))
   3. WAX_ACCOUNT: (WAX account, that is, the WAX ​​wallet address, ending with .wam)
   4. Proxy: (You can set the HTTP agent, the format is 127.0.0.1:10809, if you do not need the agent, set to null)
   5. BUILD, MINING, Chicken, COW, Plant, MBS respectively correspond to construction, collecting resources, raising chicken, random, members, members, requires operational operations, setting up to TRUE, no need to automation Operation, set to false, such as you only grow, Plant: True, all of the other is false, which reduces unnecessary network operations, improve operation efficiency
   6. Recover_ENERGY: 500 (If the energy is not enough to return to how much energy, the default 500, please prepare enough meat, the program will not automatically buy meat)
   7. Construction, collect resources, raise chicken, nurses, seeds, members, need to automate operation, set to true
   8. Other parameters are set according to your actual situation
   
8. After modifying the configuration file, double-click [main.py] to run the script, if the program exits, you can view the log in the logs folder.
9. After the script is started, a Chrome window will pop up and automatically open the FarMersWorld official website. For the first time, please log in manually. After login is successful, the script will start automation
10. If you need manual operation, do not operate in the Chrome window opened in the script, the script opens the chrome window, minimized, try not to move it, ask for hand-to-hand, please open the Chrome browser to log in to the game. The game itself can log in in multiple browsers at the same time, and will not put the game t in the script chrome.
11. Note that an account will run the script for the first time. When the script is automatically harvested, the WAX ​​wallet authorization window may pop up in the Chrome browser, and stop there, this time you need to check the automatic confirmation transaction. And agree to the transaction, so that the script will be automatically processed, in fact, the first harvesting, the first harvesting, it is necessary to automatically agree to the transaction, otherwise, each time you have to pop up the authorization window, the script is only responsible for harvesting crops. Do not deal with authorized things, auto-authorization depends on user account settings
12. Script is more open, please copy the entire source directory, modify the configuration file in another directory [user.yaml] to another account, double-click Run [main.py] to start the second script, with this, Multi-to-interference
13. Correctly shut down the program, click on the X X in the upper right corner of the script console window, will be closed, or click the script console window, press Ctrl + C, try not to close the script controlled Chrome window, otherwise WebDriver is easy to produce some zombie process


> ! ! ! If you can't open the Python file because you don't do it, you can use the command line.

### Command line run the script

> Premise is to complete the above steps, install the Python environment, install dependence

Open the command line tool (recommended to download the cmder command line tool, download link: [Click to download CMDER command line tool] (https://github.com/cmderdev/cmder/releases/download/v1.3.18/cmder_mini.zip))

Enter the project directory (assuming the project in the OpenFARMER directory of the D disk)

1. Enter d: [Press Enter] in the command line tool

2, CD D: / OpenFARMER [press Enter]

(If you do not install dependencies, you can execute python install_depends.py first.

3, python main.py [press Enter] (some environment is py main.py)

### common problem
1. The program log shows that the chicken has been successfully added, and it is successfully watered, and it has been successfully collected. Why is the game interface in Chrome still showing no bonus, no watering, no collection?

This is because the program is the operation of directly calling the intelligent contract. The game interface in Chrome will not be updated. In fact, as long as the log display operation is successful, it has been successful, and the game interface in Chrome is not updated, no need to pay attention You can reopeize a chrome window, log in to the game, and have no success.

2. Cannot log in with the Google account, prompt this browser or application may not be safe?

![image](https://Raw.githubuserContent.com/encoderlee/openfarmer/main/doc/question1.png)

This is because Chrome itself is Google home, Google judges that the Chrome browser is being controlled, and it is not safe and logged in. The solution is to log in the WAX ​​cloud money package, click [Forgot Password], enter the Google Mailpick account, reset the password according to the prompt (can be reset to the same password as the original password), can be reset, Wax cloud money package login interface, enter the Google Mail account and reset the password to log in, without a point Google icon, do not need to log in with the Google account.


### Restaurant

Welcome to reward, support me to continue to improve english version of this project.

My WAX address: bitleggerthx (account support WAX, FWW, FWF, FWG)

To support author of Chinese version use this wallets:
TRC20 address: Txmvtz3ndhpvju7symuldlbufwdxa34QIX
WAX address: OpenFARMERCN (account support WAX, FWW, FWF, FWG)

### grateful!


### Other works by the author of the basic Chinese version

> Peasant World Chinese Tutorial: [https://fww.umaske.com] (https://fww.umaske.com)
>
> Peasant World Real-Time Monitoring Chinese: [https://fw.umaske.com] (https://fw.umaske.com)
>
> [Peasant World Assistant --anchor Wallet Edition]: [https://github.com/lintan/openfarmeronanchor] (https://github.com/lintan/openfarmeronanchor)
