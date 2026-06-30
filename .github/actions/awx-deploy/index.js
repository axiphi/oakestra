const core = require('@actions/core');
const axios = require('axios');
const https = require('https');
const sslRootCAs = require('ssl-root-cas');


async function triggerAWX() {
  try {

    // Add SSL root CAs to the global HTTPS agent
    https.globalAgent.options.ca = sslRootCAs.create();


    const awxUrl = core.getInput('AWX_URL');
    const token = core.getInput('AWX_TOKEN');
    const workflowTemplateId = core.getInput('AWX_TEMPLATE_ID');
    const pullRequestBranch = core.getInput('PR_BRANCH');
    const pullRequestCommit = core.getInput('PR_COMMIT');
    const pullRequestUser = core.getInput('PR_USER');
    const forkRepo = core.getInput('FORK_REPO');

    const headers = {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    };

    const extraVars = {
      oak_repo_branch: pullRequestBranch,
      oak_repo_commit: pullRequestCommit,
      oak_branch: pullRequestBranch, //compatibility with oak custom workflow
      oak_commit: pullRequestCommit, //compatibility with oak custom workflow
      pr_fork_user: pullRequestUser,
      pr_fork_repo: forkRepo //compatibility for PRs coming from forks
    };

    // Print the URL, template ID, branch, and commit
    console.log(`🌱 Branch: ${pullRequestBranch}`);
    console.log(`#️⃣ Commit: ${pullRequestCommit}`);
    console.log(`👷 PR Commit Author: ${pullRequestUser}`);

    // Step 1: Trigger the workflow job template
    const jobLaunchUrl = `https://${awxUrl}/api/v2/workflow_job_templates/${workflowTemplateId}/launch/`;
    const response = await axios.post(jobLaunchUrl, { extra_vars: extraVars }, { headers });

    const jobId = response.data.workflow_job;  // ID of the launched job

    console.log(`🆔 Execution ID: ${jobId}`);

    // Step 2: Poll the job status
    const jobStatusUrl = `https://${awxUrl}/api/v2/workflow_jobs/${jobId}/`;
    let status = '';

    while (true) {
      const jobResponse = await axios.get(jobStatusUrl, { headers });
      status = jobResponse.data.status;

      console.log(`⚙️ Current job status: ${status} ⏳`);

      if (status === 'successful') {
        console.log('🎉 ✅ 🎉  Tests passed successfully! 🎉 ✅ 🎉');
        return;
      } else if (['failed', 'error', 'canceled'].includes(status)) {
        throw new Error(` 🔴 Tests execution failed with status: ${status} 🔴 `);
      }

      // Wait for 1 minute before checking the status again
      await new Promise(resolve => setTimeout(resolve, 60000));
    }

  } catch (error) {
    core.setFailed(`Action failed: ${error.message}`);
  }
}

triggerAWX();
