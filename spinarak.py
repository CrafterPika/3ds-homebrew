#! /usr/bin/python3
### 4TU Tools: spinarak.py by CompuCat, LyfeOnEdge, and the 4TU Team
import os, sys, json, shutil, argparse, fnmatch
from datetime import datetime
import urllib.request
from zipfile import ZipFile, ZIP_DEFLATED

version='0.0.8'

config_default = """# spinarak config
target_dir = "."
output_dir = "public"
valid_binary_extensions = [".nro", ".elf", ".rpx", ".cia", ".3dsx", "none"]
"""

#Build opener that prevents failed retrieves on some sites
opener = urllib.request.build_opener()
opener.addheaders = [('User-agent', 'Mozilla/5.0')]
urllib.request.install_opener(opener)

if not os.path.isfile(os.path.join(os.path.dirname(__file__), "config.py")):
	with open(os.path.join(os.path.dirname(__file__), "config.py"), 'w+') as cfg:
		cfg.write(config_default)

global config
import config

# Original zipit code:
# http://stackoverflow.com/a/6078528
#
# Call `zipit` with the path to either a directory or a file.
# All paths packed into the zip are relative to the directory
# or the directory of the file.
# Modified to take a list of filepaths to the given path to exclude
def zipit(path, archname, exclude = None):
	# Create a ZipFile Object primed to write
	archive = ZipFile(archname, "w", ZIP_DEFLATED) # "a" to append, "r" to read
	# Recurse or not, depending on what path is
	if os.path.isdir(path):
		zippy(path, archive, exclude)
	else:
		archive.write(path)
	archive.close()
	return "Compression of \""+path+"\" was successful!"

def zippy(path, archive, exclude = None):
	paths = os.listdir(path)
	for p in paths:
		p = os.path.join(path, p) # Make the path relative
		if os.path.isdir(p): # Recursive case
			zippy(p, archive)
		else:
			if exclude and p in exclude:
				continue
			archive.write(p) # Write the file to the zipfile
	return

### Methods, etc.
def underprint(x): print(x+"\n"+('-'*len(x.strip()))) #Prints with underline. Classy, eh?

def get_size(start_path): #I do love my oneliners. Oneliner to get the size of a directory recursively.
	return sum([sum([os.path.getsize(os.path.join(dirpath,f)) for f in filenames if not os.path.islink(os.path.join(dirpath,f))]) for dirpath, dirnames, filenames in os.walk(start_path)])

def remove_prefix(text, prefix): #thanks SE for community-standard method, strips prefix from string
	if text.startswith(prefix):
		return text[len(prefix):]
	return text

#Download a file at a url, returns file path
def download(fileURL, filename = None): #filename): 
	try:
		if filename:
			downloadedfile, headers = urllib.request.urlretrieve(fileURL, filename)
		else:
			downloadedfile, headers = urllib.request.urlretrieve(fileURL)
		return downloadedfile
	except Exception as e: 
		print(f"\n\tError downloading file at - {fileURL} - to - {filename}\n\t{e}")

class Spinner:
	def __init__(self, target_dir, output_dir, ignore_non_empty_output = False):
		self.target_dir = os.path.realpath(target_dir)
		self.output_dir = os.path.realpath(output_dir)
		self.ignore_non_empty_output = ignore_non_empty_output
		#Instantiate output directory if needed and look for pre-existing libget repo.
		self.repo_buildable = False
		self.updatingRepo = False #This flag is True if and only if the output directory is a valid libget repo; it tells Spinarak to skip repackaging packages that haven't changed.
		if os.path.isdir(self.output_dir):
			if len(os.listdir(self.output_dir)) == 0: pass
			else:
				try:
					json.load(open(os.path.join(self.output_dir, "repo.json")))
					self.repo_buildable = True
					self.updatingRepo = True
					print("INFO: the output directory is already a libget repo! Updating the existing repo.")
				except:
					if not self.ignore_non_empty_output:
						print("ERROR: output directory is not empty and is not a libget repo. Repo may not be spun.\n\t- The '-i' argument can bypass this check.")
						return
					else:
						self.repo_buildable = True
		else: 
			os.makedirs(self.output_dir)
			self.repo_buildable = True

		if not os.path.isdir(os.path.join(self.output_dir, "zips")):
			os.mkdir(os.path.join(self.output_dir, "zips"))

	def spin(self):
		if not self.repo_buildable:
			print("ERROR: Repo is not buildable, not continuing...")
			return
		repojson={'packages':[]} #Instantiate repo.json format
		failedPackages=[]
		skippedPackages=[]

		packages = self.get_packages_by_path(self.target_dir)
		if not packages:
			return print("Failed to build repo - No package metadata found in target directory")
		if self.updatingRepo:
			previousRepojson = json.load(open(os.path.join(self.output_dir+"repo.json")))

		for pkgname, pkgpath in packages:
			#TODO: avoid rebuilding packages that haven't actually changed.
			#Open and validate pkgbuild
			try:
				pkgbuild=json.load(open(os.path.join(pkgpath,"pkgbuild.json"))) #Read pkgbuild.json
				for x in ('category','package','license','title','url','author','version','details','description'): #Check for required components
					if x not in pkgbuild and x not in pkgbuild['info']: raise LookupError("pkgbuild.json is missing the "+x+" component.")
			except Exception as e:
				 failedPackages.append(pkgname)
				 print("ERROR: failed to build "+pkgname+"! Error message: "+str(e)+"\n")
				 continue
			print("\n") #Can't put in the underprint since it calls strip() on the input
			if self.updatingRepo: #Avoid rebuilding packages that haven't changed.
				prevPkgInfo = next(((pkg for pkg in previousRepojson['packages'] if pkg['name'] == pkgbuild['package'])), None) #Search for existing package
				if prevPkgInfo == None: underprint("Now packaging: "+pkgbuild['info']['title'])
				else:
					if prevPkgInfo['version'] == pkgbuild['info']['version']:
						print(pkgbuild['info']['title']+" hasn't changed, skipping.\n")
						skippedPackages.append(pkgname)
						repojson['packages'].append(prevPkgInfo) #Copy package info from previous repo.json
						continue
					else:
						underprint("Now updating: "+pkgbuild['info']['title'])
						os.remove(os.path.join(self.output_dir,"zips",pkgname,".zip"))
			else: underprint("Now packaging: "+pkgbuild['info']['title'])
			manifest=open(os.path.join(self.target_dir, pkgname, "manifest.install"), 'w')

			print(str(len(pkgbuild['assets']))+" asset(s) detected")
			for asset in pkgbuild['assets']: self.handle_asset(pkgname, asset, manifest)

			pkginfo={ #Format package info
				'category': pkgbuild['info']['category'],
				'name': pkgbuild['package'],
				'license': pkgbuild['info']['license'],
				'title': pkgbuild['info']['title'],
				'url': pkgbuild['info']['url'],
				'author': pkgbuild['info']['author'],
				'version': pkgbuild['info']['version'],
				'details': pkgbuild['info']['details'],
				'description': pkgbuild['info']['description'],
				'updated': str(datetime.utcfromtimestamp(os.path.getmtime(os.path.join(self.target_dir, pkgname, "pkgbuild.json"))).strftime('%Y-%m-%d')),
			}
			try: pkginfo['changelog']=pkgbuild['changelog']
			except:
				if 'changes' in pkgbuild:
					pkginfo['changelog']=pkgbuild['changes']
					print("WARNING: the `changes` field was deprecated from the start. Use `changelog` instead.")
				else: print("WARNING: no changelog found!")
			with open(os.path.join(self.target_dir, pkgname, "info.json"), "w+") as info:
				json.dump(pkginfo, info, indent=1) # Output package info to info.json
			manifest.close()
			print("manifest.install generated.")
			print("Package is "+str(get_size(os.path.join(self.target_dir, pkgname))//1024)+" KiB large.")

			zipit(os.path.join(self.target_dir, pkgname), os.path.join(self.output_dir, "zips", f"{pkgname}.zip"), exclude = ["pkgbuild.json"]) # Make package zip

			print("Package written to "+self.output_dir+"/zips/"+pkgname+".zip")
			print("Zipped package is "+str(os.path.getsize(os.path.join(self.output_dir, "zips", f"{pkgname}.zip"))//1024)+" KiB large.")

			repo_extended_info={ #repo.json has package info plus extended info
				'extracted': get_size(pkgname)//1024,
				'filesize': os.path.getsize(self.output_dir+"/zips/"+pkgname+".zip")//1024,
				'web_dls': -1, #TODO: get these counts from stats API
				'app_dls': -1 #TODO
			}
			#Attempt to read binary path from pkgbuild; otherwise, guess it.
			try: repo_extended_info['binary']=pkgbuild['info']['binary']
			except:
				if pkginfo['category']=="theme":
					repo_extended_info['binary']="none"
					print("INFO: binary path not specified. Category is theme, so autofilling \"none\".")
				else:
					broken=False
					for (dirpath, dirnames, filenames) in os.walk(os.path.join(self.target_dir, pkgname)):
						for file in filenames:
							if file.endswith(tuple(config.valid_binary_extensions)):
								repo_extended_info['binary']=os.path.join(dirpath,file)[os.path.join(dirpath,file).index("/"):]
								broken=True
								break
							if broken: break
					if not broken: print("WARNING: "+pkgbuild['info']['title']+"'s binary path not specified in pkgbuild.json, and no binary found!")
					else: print("WARNING: binary path not specified in pkgbuild.json; guessing "+repo_extended_info['binary']+".")
			repo_extended_info.update(pkginfo) #Add package info and extended info together

			repojson['packages'].append(repo_extended_info) #Append package info to repo.json
			print() #Console newline at end of package. for prettiness

		underprint("\nSUMMARY")
		print("Built "+str(len(packages)-len(failedPackages)-len(skippedPackages))+" of "+str(len(packages))+" packages.")
		if len(failedPackages)>0: print("Failed packages: "+str(failedPackages))
		if len(skippedPackages)>0: print("Skipped packages: "+str(skippedPackages))
		print("All done. Enjoy your new repo :)")

	def handle_asset(self, pkg, asset, manifest, prepend="\t"): #Downloads and places a given asset.
		asset_file = None
		if os.path.isfile(os.path.join(self.target_dir, pkg, asset['url'])): # Check if file exists locally
			print(prepend+"Asset is local.")
			asset_file = os.path.join(self.target_dir, pkg, asset['url'])
		else: # Download asset from URL
			print(prepend+"Downloading "+asset['url']+"...", end="")
			sys.stdout.flush()
			asset_file = download(asset['url'])
			if not asset_file: return #If a download failed don't continue to try to process the asset
			print("done.")
			#asset_file_path=pkg+'/temp_asset'
		if asset['type'] in ('update', 'get', 'local', 'extract'):
			print(prepend+"- Type is "+asset['type']+", moving to /"+asset['dest'].strip("/"))
			manifest.write(asset['type'].upper()[0]+": "+asset['dest'].strip("/")+"\n")
			os.makedirs(os.path.dirname(os.path.join(self.target_dir, pkg, asset["dest"].strip("/"))), exist_ok=True)
			shutil.copyfile(asset_file, os.path.join(self.target_dir, pkg, asset["dest"].strip("/")))
		elif asset['type'] == 'icon':
			print(prepend+"- Type is icon, moving to /icon.png")
			if not os.path.normpath(asset_file) == os.path.normpath(os.path.join(self.target_dir, pkg, 'icon.png')):
				shutil.copyfile(asset_file, os.path.join(self.target_dir, pkg, 'icon.png'))
			os.makedirs(os.path.join(self.output_dir, 'packages', pkg), exist_ok=True)
			shutil.copyfile(os.path.join(self.target_dir, pkg, 'icon.png'), os.path.join(self.output_dir, 'packages', pkg, 'icon.png'))
		elif asset['type'] == 'screenshot':
			print(prepend+"- Type is screenshot, moving to /screen.png")
			if not os.path.normpath(asset_file) == os.path.normpath(os.path.join(self.target_dir, pkg, 'screen.png')):
				shutil.copyfile(asset_file, os.path.join(self.target_dir, pkg, 'screen.png'))
			os.makedirs(os.path.join(self.output_dir, 'packages', pkg), exist_ok=True)
			shutil.copyfile(os.path.join(self.target_dir, pkg, 'screen.png'), os.path.join(self.output_dir, 'packages', pkg, 'screen.png'))

		elif asset['type'] == 'zip':
			print(prepend+"- Type is zip, has "+str(len(asset['zip']))+" sub-asset(s)")
			with ZipFile(asset_file, "r") as asset_zip:
				zip_files = asset_zip.namelist()
				handledSubAssets=0
				for subasset in asset["zip"]:
					subasset_files = [f for f in zip_files if fnmatch.fnmatch(f, subasset["path"]) and not f.endswith("/")]
					if not subasset_files:
						print(prepend + f"No valid assets found in zip for pattern {subasset}")
					for f in subasset_files:
						self.handle_zip_asset(pkg, subasset, manifest, f, asset_zip, prepend = prepend + "\t")
						handledSubAssets+=1
				if handledSubAssets!=len(asset['zip']): print("INFO: discrepancy in subassets handled vs. listed. "+str(handledSubAssets)+" handled, "+str(len(asset['zip']))+" listed.")
		else: print("ERROR: asset of unknown type detected. Skipping.")

	def handle_zip_asset(self, pkg, asset, manifest, zip_member, zip_object, prepend = "\t"):
		print(f"{prepend}Handling zip asset - {zip_member}")
		print(prepend+"- Type is "+asset['type']+", moving to /"+asset['dest'].strip("/"))
		if asset["type"] in ('update', 'get', 'local', 'extract'): 
			manifest.write(asset['type'].upper()[0]+": "+asset['dest'].strip("/")+"\n")
			os.makedirs(os.path.dirname(os.path.join(self.target_dir, pkg, asset["dest"].strip("/"))), exist_ok=True) # Make package output dir
			if asset['dest'].endswith("/"): #If the destination is a dir, extract to dir
				zip_object.extract(zip_member, path = os.path.join(self.target_dir, pkg, asset["dest"].strip("/")))
			else: #Otherwise extract file
				zip_object.extract(zip_member, path = os.path.dirname(os.path.join(self.target_dir, pkg, asset["dest"].strip("/"))))
		else: 
			print(f"{prepend}ERROR: asset of unsupported type detected in zip asset. Skipping...")
			asset_data = json.dumps(asset, indent = 4).replace("\n", f"\n{prepend}\t")
			print(f"{prepend}ERRORING ASSET: {asset_data}")

	def get_packages_by_path(self, target):
		target = os.path.realpath(target)
		packages = []
		for root, dirs, files in os.walk(target, topdown=False):
			for name in dirs:
				if os.path.isfile(os.path.join(root, name, "pkgbuild.json")):
					packages.append((name, os.path.join(root, name)))
		return packages
	
if __name__ == "__main__":
	underprint("This is Spinarak v"+version+" by CompuCat and the 4TU Team.")

	parser = argparse.ArgumentParser(description='Spinarak by CompuCat, LyfeOnEdge, and the 4TU Team.\n\tBuild libget repositories from pkgbuild metadata repositories.')
	parser.add_argument("-o", "--output", help = "Repository output directory")
	parser.add_argument("-t", "--target", help = "Target metadata repoistory directory")
	parser.add_argument("-i", "--ignore_non_empty_output", action = "store_true", help = "Ignore error raised when trying to build a repo for the first time in a non-empty output dir")
	args = parser.parse_args()

	#Prioritize passed args over config
	target = args.target or config.target_dir
	output = args.output or config.output_dir

	spinner = Spinner(target, output, args.ignore_non_empty_output)
	spinner.spin()