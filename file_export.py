import os

def selective_export(output_file="project_context.txt"):
    """Export key files with better organization."""
    
    # Define which files to include (customize this list)
    important_files = [
        'src/components/QuestionCard.tsx',
        'src/contexts/InterviewContext.tsx', 
        'src/pages/UploadPage.tsx',
        'src/pages/InterviewPage.tsx',
        'src/services/api.ts',
        'package.json',
        'src\App.tsx',
        'src\main.tsx',
        'backend\main.py',
    ]
    
    with open(output_file, 'w', encoding='utf-8') as outfile:
        outfile.write("PROJECT CONTEXT FOR AI CHATBOT\n")
        outfile.write("=" * 60 + "\n\n")
        
        for file_path in important_files:
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as infile:
                        content = infile.read()
                    
                    outfile.write(f"FILE: {file_path}\n")
                    outfile.write("-" * 40 + "\n")
                    outfile.write(content)
                    outfile.write("\n\n" + "=" * 60 + "\n\n")
                    
                    print(f"✓ Added: {file_path}")
                    
                except Exception as e:
                    print(f"✗ Error reading {file_path}: {e}")
            else:
                print(f"✗ File not found: {file_path}")
    
    print(f"\nProject context exported to {output_file}")

if __name__ == "__main__":
    selective_export()