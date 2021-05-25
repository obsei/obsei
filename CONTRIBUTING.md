# 👐 Contributing to Obsei

First off, thank you for even considering contributing to this package, every contribution big or small is greatly appreciated. 
Community contributions are what keep projects like this fueled and constantly improving, so a big thanks to you!

Below are some sections detailing the guidelines we'd like you to follow to make your contribution as seamless as possible.

- [Code of Conduct](#coc)
- [Asking a Question and Discussions](#question)
- [Issues, Bugs, and Feature Requests](#issue)
- [Submission Guidelines](#submit)
- [Code Style and Formatting](#code)

## 📜 <a name="coc"></a> Code of Conduct
The [Code of Conduct](https://github.com/lalitpagaria/obsei/blob/master/CODE_OF_CONDUCT.md) applies within all community spaces. 
If you are not familiar with our Code of Conduct policy, take a minute to read the policy before starting with your first contribution.

## 🗣️ <a name="question"></a> Query or Discussion

We would like to use [Github discussions](https://github.com/lalitpagaria/obsei/discussions) as the central hub for all 
community discussions, questions, and everything else in between. While Github discussions is a new service (as of 2021) 
we believe that it really helps keep this repo as one single source to find all relevant information. Our hope is that 
discussion page functions as a record of all the conversations that help contribute to the project's development.

If you are new to [Github discussions](https://github.com/lalitpagaria/obsei/discussions) it is a very similar experience 
to Stack Overflow with an added element of general discussion and discourse rather than solely being question and answer based.

## 🪲 <a name="issue"></a> Issues, Bugs, and Feature Requests

We are very open to community contributions and appreciate anything that improves **Obsei**. This includes fixings typos, adding missing documentation, fixing bugs or adding new features.
To avoid unnecessary work on either side, please stick to the following process:

1. If you feel like your issue is not specific and more of a general question about a design decision, or algorithm implementation maybe start a [discussion](https://github.com/lalitpagariai/obsei/discussions) instead, this helps keep the issues less cluttered and encourages more open-ended conversation.
2. Check if there is already [an related issue](https://github.com/lalitpagariai/obsei/issues).
3. If there is not, open a new one to start a discussion. Some features might be a nice idea, but don't fit in the scope of Obsei and we hate to close finished PRs.
4. If we came to the conclusion to move forward with your issue, we will be happy to accept a pull request. Make sure you create a pull request in an early draft version and ask for feedback. 
5. Verify that all tests in the CI pass (and add new ones if you implement anything new)

See [below](#submit) for some guidelines.

##  ✉️  <a name="submit"></a> Submission Guidelines

### Submitting an Issue

Before you submit your issue search the archive, maybe your question was already answered. 

If your issue appears to be a bug, and hasn't been reported, open a new issue.
Help us to maximize the effort we can spend fixing issues and adding new
features, by not reporting duplicate issues. Providing the following information will increase the
chances of your issue being dealt with quickly:

- **Describe the bug** - A clear and concise description of what the bug is.
- **To Reproduce**- Steps to reproduce the behavior.
- **Expected behavior** - A clear and concise description of what you expected to happen.
- **Environment**
  - Obsei version
  - Python version
  - OS
- **Suggest a Fix** - if you can't fix the bug yourself, perhaps you can point to what might be
  causing the problem (line of code or commit)

When you submit a PR you will be presented with a PR template, please fill this in as best you can.

### Submitting a Pull Request

Before you submit your pull request consider the following guidelines:

- Search [GitHub](https://github.com/lalitpagariai/obsei/pulls) for an open or closed Pull Request
  that relates to your submission. You don't want to duplicate effort.
- Fork the main repo if not already done
- Rebase fork with `upstream master`
- Create new branch and add the changes in that branch
- Add supporting test cases
- Follow our [Coding Rules](#rules).
- Avoid checking in files that shouldn't be tracked (e.g `dist`, `build`, `.tmp`, `.idea`). 
  We recommend using a [global](#global-gitignore) gitignore for this.
- Before you commit please run the test suite and make sure all tests are passing.
- Format your code appropriately:
  * This package uses [black](https://black.readthedocs.io/en/stable/) as its formatter. 
    In order to format your code with black run ```black . ``` from the root of the package.
- Commit your changes using a descriptive commit message.
- In GitHub, send a pull request to `obsei:master`.
- If we suggest changes then:
  - Make the required updates.
  - Rebase your branch and force push to your GitHub repository (this will update your Pull Request):

That's it! Thank you for your contribution!


## ✅ <a name="rules"></a> Coding Rules

We generally follow the [Google Python style guide](http://google.github.io/styleguide/pyguide.html).

----

*This guide was inspired by the [transformers-interpret](https://github.com/cdpierse/transformers-interpret/blob/master/CONTRIBUTING.md)
and [Haystack](https://github.com/deepset-ai/haystack/blob/master/CONTRIBUTING.md)*
