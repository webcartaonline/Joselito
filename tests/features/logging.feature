Feature: Application logging (US 9.1)
  As a support person
  I want the application to keep a record of what happens
  So that I can diagnose problems when something fails

  Scenario: Relevant events are logged during a run
    Given the logging is configured in a temporary folder
    When I run a research session for the topic "Python"
    Then the log records the pipeline stages
    And the log file exists

  Scenario: Every record has a date and a severity level
    Given the logging is configured in a temporary folder
    When I run a research session for the topic "Python"
    Then every log line has a date and a level

  Scenario: A failure is logged
    Given the logging is configured in a temporary folder
    And the Wikipedia source cannot find the article
    When I run a research session for the topic "Python"
    Then the log records an error

  Scenario: Sensitive data is not logged
    Given the logging is configured in a temporary folder
    And the Wikipedia source fails with a Hugging Face token
    When I run a research session for the topic "Python"
    Then the log does not contain the token
