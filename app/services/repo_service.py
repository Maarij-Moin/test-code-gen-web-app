import os 
import git 

Base_DIR = "repo"

def clone_repo(repo_url: str) -> str:
    repo_name = repo_url.split("/")[-1].replace(".git", "")
    repo_path = os.path.join(Base_DIR, repo_name)
    
    if not os.path.exists(Base_DIR):
        os.makedirs(Base_DIR)
    
    
    if not os.path.exists(repo_path):
        git.Repo.clone_from(repo_url, repo_path)
        
    return repo_path
        