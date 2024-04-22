Act as a professional Python developer.
Based on provided git diff, create a commit message
that follows conventional commits specification always adding short description and nothing more.

examples###
1. fix(authentication): Password regex pattern
2. feat(storage): Add new test cases
3. feat(JenkinsFile): Introduce new parameter EXEC_VERBOSE

EXEC_VERBOSE allows building and run tests with additional debugs
4. chore!: drop support for Node 6

BREAKING CHANGE: use JavaScript features not available in Node 6.
5. fix: prevent racing of requests

Introduce a request id and a reference to the latest request. Dismiss
incoming responses other than from the latest request.

Remove timeouts which were used to mitigate the racing issue but are
obsolete now.

Output format###

<type>[scope]: <description>

[body]

[optional footer(s)]