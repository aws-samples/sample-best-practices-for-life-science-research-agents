def pretty_print_paperqa_results(answer) -> None:
    """Pretty print the output from the PaperQA2 query."""
    session_output = answer.session

    print("**Question**\n")
    print(session_output.question + "\n")
    print("**Answer**\n")
    print(session_output.answer + "\n")
    print("**Evidence**\n")
    for context in session_output.contexts:
        print(f"{context.text.name}:\t{context.context}")
    print("**Token Counts**\n")
    print(f"{'Model':<45} {'Input':<8} {'Output':<8}")
    print("-" * 65)
    for model, values in session_output.token_counts.items():
        print(f"{model:<45} {values[0]:<8} {values[1]:<8}")
    print()
    print("**Estimated Cost**\n")
    print(round(session_output.cost, 3))