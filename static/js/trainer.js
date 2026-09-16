document.addEventListener("DOMContentLoaded", () => {


    // =====================================================
    // DELETE EXTRACTED COMMENTS
    // =====================================================

    const extractedContainer =
        document.getElementById("extracted-comments");


    if (extractedContainer) {

        extractedContainer.addEventListener(
            "click",
            (event) => {

                const deleteButton =
                    event.target.closest(".delete-button");

                if (!deleteButton) {
                    return;
                }

                const row =
                    deleteButton.closest(".comment-row");

                if (!row) {
                    return;
                }

                row.remove();

                renumberComments();
            }
        );

    }


    function renumberComments() {

        if (!extractedContainer) {
            return;
        }

        const rows =
            extractedContainer.querySelectorAll(
                ".comment-row"
            );

        rows.forEach((row, index) => {

            const number =
                row.querySelector(".comment-number");

            if (number) {
                number.textContent =
                    `#${index + 1}`;
            }

        });

    }



    // =====================================================
    // REMOVE EMPTY COMMENTS BEFORE ANALYSIS
    // =====================================================

    const extractedForms =
        document.querySelectorAll(
            'form input[name="action"][value="analyze_extracted"]'
        );


    extractedForms.forEach((actionInput) => {

        const form =
            actionInput.closest("form");

        if (!form) {
            return;
        }

        form.addEventListener(
            "submit",
            () => {

                const textareas =
                    form.querySelectorAll(
                        ".extracted-input"
                    );

                textareas.forEach((textarea) => {

                    if (!textarea.value.trim()) {

                        textarea.disabled = true;

                    }

                });

            }
        );

    });



    // =====================================================
    // ACCEPT ALL AI SUGGESTIONS
    // =====================================================

    const acceptAllButton =
        document.getElementById("accept-all");


    if (acceptAllButton) {

        acceptAllButton.addEventListener(
            "click",
            () => {

                const predictionRows =
                    document.querySelectorAll(
                        ".prediction-row"
                    );


                predictionRows.forEach((row) => {

                    const modelPrediction =
                        row.querySelector(
                            ".prediction-model strong"
                        );

                    if (!modelPrediction) {
                        return;
                    }


                    const predictedLabel =
                        modelPrediction.textContent
                            .trim()
                            .toLowerCase();


                    const radios =
                        row.querySelectorAll(
                            'input[type="radio"]'
                        );


                    radios.forEach((radio) => {

                        if (
                            predictedLabel === "toxic" &&
                            radio.value === "1"
                        ) {

                            radio.checked = true;

                        }


                        if (
                            predictedLabel === "non-toxic" &&
                            radio.value === "0"
                        ) {

                            radio.checked = true;

                        }

                    });

                });

            }
        );

    }



    // =====================================================
    // AUTO-RESIZE EXTRACTED COMMENT BOXES
    // =====================================================

    const extractedInputs =
        document.querySelectorAll(
            ".extracted-input"
        );


    extractedInputs.forEach((textarea) => {

        const resize = () => {

            textarea.style.height = "auto";

            textarea.style.height =
                `${textarea.scrollHeight}px`;

        };


        textarea.addEventListener(
            "input",
            resize
        );


        resize();

    });

});