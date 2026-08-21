from SocialScienceResearch.domain.collection import CollectionSpec, CollectionTarget
from SocialScienceResearch.config.settings import SocialScienceSettings

spec = CollectionSpec(targets=[CollectionTarget(kind='video', url='https://x/y')], scrape_all_comments=True)
effective = spec.effective(SocialScienceSettings())
print('Test 1 - scrape_all_comments=True:')
print('  max_comments_per_video:', effective['max_comments_per_video'])
print('  scrape_all_comments:', effective['scrape_all_comments'])

spec2 = CollectionSpec(targets=[CollectionTarget(kind='video', url='https://x/y')], scrape_all_comments=False)
effective2 = spec2.effective(SocialScienceSettings())
print('Test 2 - scrape_all_comments=False:')
print('  max_comments_per_video:', effective2['max_comments_per_video'])
print('  scrape_all_comments:', effective2['scrape_all_comments'])

spec3 = CollectionSpec(targets=[CollectionTarget(kind='video', url='https://x/y')])
effective3 = spec3.effective(SocialScienceSettings())
print('Test 3 - scrape_all_comments=None (default):')
print('  max_comments_per_video:', effective3['max_comments_per_video'])
print('  scrape_all_comments:', effective3['scrape_all_comments'])