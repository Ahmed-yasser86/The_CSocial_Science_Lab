import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from Nodes.IdentityResearchNode import make_identity_research


async def main():
    query_text = "mostafa el adawy the egyptian salafai"
    mock_state = {
        "chain_input": {
            "query": query_text
        }
    }

    print("🚀 Starting Independent Identity Research Test...")
    print(f"Target Query: {query_text}\n" + "-"*50)

    try:
        # تنفيذ الدالة المستوردة (التي تُرجع الهيكل المتداخل identity_data)
        output_state = await make_identity_research(mock_state)

        # استخراج البيانات من الهيكل المتداخل
        identity_data = output_state["identity_data"]
        report_content = identity_data["report"]
        sources = identity_data["sources"]
        costs = identity_data["costs"]

        # طباعة النتائج بشكل منسق وواضح على الشاشة
        print("\n" + "="*20 + " IDENTITY REPORT " + "="*20)
        print(report_content)
        print("="*55 + "\n")

        print("🔗 Source URLs:")
        for url in sources:
            print(f" - {url}")

        print(f"\n💰 Total Estimated Cost: ${costs}")
        
        # حفظ المخرجات في ملف Markdown (.md)
        safe_filename = "".join([c if c.isalnum() else "_" for c in query_text])
        file_path = f"{safe_filename}_report.md"
        
        with open(file_path, "w", encoding="utf-8") as f:
            # إضافة عنوان للتقرير
            f.write(f"# Identity Report: {query_text}\n\n")
            # كتابة محتوى التقرير
            f.write(report_content + "\n\n")
            
            # كتابة المصادر
            f.write("---\n### 🔗 Source URLs:\n")
            for url in sources:
                f.write(f"- {url}\n")
                
            # كتابة التكلفة
            f.write(f"\n### 💰 Total Estimated Cost: ${costs}\n")
            
        print(f"\n📁 Report successfully saved to: {file_path}")

        print("\n✅ Test Completed Successfully!")

    except Exception as e:
        print(f"\n❌ An error occurred during the test: {e}")


if __name__ == "__main__":
    asyncio.run(main())