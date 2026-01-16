/**
 * KlubFlow Reddit Queue Monitor
 * 
 * This Devvit app monitors posts with "LIVE QUEUE UPDATES" flair
 * in r/Berghain_Community and sends raw messages to the KlubFlow backend.
 * 
 * All parsing is done on the backend for consistency with Telegram data.
 */

import { Devvit, TriggerContext, ScheduledJobEvent } from '@devvit/public-api';

// Configure the app
Devvit.configure({
  redditAPI: true,
  http: true,
});

// KlubFlow backend URL (update when deployed)
const KLUBFLOW_API_URL = 'https://your-backend.herokuapp.com';

/**
 * Send raw message to KlubFlow backend for parsing
 */
async function sendToBackend(data: {
  source: string;
  source_id: string;
  content: string;
  author_name?: string;
  source_timestamp?: string;
}) {
  try {
    const response = await fetch(`${KLUBFLOW_API_URL}/api/queue/reddit-update`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Source': 'devvit-klubflow',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      console.error('Failed to send to backend:', response.status);
      return false;
    }
    
    const result = await response.json();
    console.log('Backend response:', result);
    return result.success;
  } catch (error) {
    console.error('Error sending to backend:', error);
    return false;
  }
}

/**
 * Check if a post is a queue update thread
 */
function isQueueUpdatePost(flairText: string, title: string): boolean {
  const flair = flairText.toLowerCase();
  const titleLower = title.toLowerCase();
  
  return (
    flair.includes('live queue') ||
    flair.includes('queue update') ||
    (titleLower.includes('queue') && titleLower.includes('update')) ||
    (titleLower.includes('klubnacht') && titleLower.includes('queue'))
  );
}

/**
 * Trigger: When a new comment is posted
 */
Devvit.addTrigger({
  event: 'CommentCreate',
  onEvent: async (event, context) => {
    const comment = event.comment;
    if (!comment) return;

    const post = await context.reddit.getPostById(event.postId!);
    const flairText = post.linkFlair?.text || '';
    
    if (!isQueueUpdatePost(flairText, post.title)) {
      return;
    }

    console.log('Found comment in queue thread:', comment.id);

    await sendToBackend({
      source: 'reddit',
      source_id: `comment_${comment.id}`,
      content: comment.body,
      author_name: comment.authorName,
      source_timestamp: new Date(comment.createdAt).toISOString(),
    });
  },
});

/**
 * Trigger: When a new post is created
 */
Devvit.addTrigger({
  event: 'PostCreate',
  onEvent: async (event, context) => {
    const post = event.post;
    if (!post) return;

    const flairText = post.linkFlair?.text || '';
    
    if (!isQueueUpdatePost(flairText, post.title)) {
      return;
    }

    console.log('Found queue update post:', post.id);

    const content = post.body ? `${post.title}\n\n${post.body}` : post.title;
    
    await sendToBackend({
      source: 'reddit',
      source_id: `post_${post.id}`,
      content: content,
      author_name: post.authorName,
      source_timestamp: new Date(post.createdAt).toISOString(),
    });
  },
});

/**
 * Scheduled job: Periodically scan for updates
 */
Devvit.addSchedulerJob({
  name: 'scan_queue_updates',
  onRun: async (event: ScheduledJobEvent, context: TriggerContext) => {
    console.log('Running scheduled queue scan...');
    
    const subreddit = await context.reddit.getCurrentSubreddit();
    const posts = await subreddit.getNew({ limit: 10 });
    
    let processedCount = 0;
    
    for await (const post of posts) {
      const flairText = post.linkFlair?.text || '';
      
      if (!isQueueUpdatePost(flairText, post.title)) {
        continue;
      }
      
      const comments = await post.comments.getNew({ limit: 50 });
      
      for await (const comment of comments) {
        const commentAge = Date.now() - comment.createdAt.getTime();
        if (commentAge > 15 * 60 * 1000) continue;
        
        const sent = await sendToBackend({
          source: 'reddit',
          source_id: `comment_${comment.id}`,
          content: comment.body,
          author_name: comment.authorName,
          source_timestamp: new Date(comment.createdAt).toISOString(),
        });
        
        if (sent) processedCount++;
      }
    }
    
    console.log(`Scan complete. Processed ${processedCount} comments.`);
  },
});

/**
 * Menu action: Manually trigger a scan
 */
Devvit.addMenuItem({
  label: '🔄 Scan for Queue Updates',
  location: 'subreddit',
  onPress: async (event, context) => {
    context.ui.showToast('Scanning for queue updates...');
    
    await context.scheduler.runJob({
      name: 'scan_queue_updates',
      runAt: new Date(),
    });
    
    context.ui.showToast('✅ Scan complete!');
  },
});

export default Devvit;
