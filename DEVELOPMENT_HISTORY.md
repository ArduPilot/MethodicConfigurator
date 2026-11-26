# Development history

In the beginning of the development of this software we used development techniques from the automotive industry.
We used the [standard V-Model software development method](https://en.wikipedia.org/wiki/V-model_(software_development)).
It was augmented with [DevOps](https://en.wikipedia.org/wiki/DevOps) and [CI/CD automation](https://en.wikipedia.org/wiki/CI/CD) practices at a later stage.

## V-model

Development started by using the classic V-model development methodology.

```mermaid
flowchart TB
    subgraph requirements["Requirements & Design"]
        direction LR
        Z([User Requirements]) --> A
        A([System Requirements]) --> B([Software Architecture])
        B --> C([Module Design])
    end

    subgraph testing["Testing"]
        direction LR
        F --> G([Acceptance Testing])
        E --> F([System Testing])
        D([Module Testing]) --> E([Integration Testing])
    end

    %% V-shape connections (crossing levels)
    Z --> G
    A --> F
    B --> E
    C --> D

    %% Clickable links
    click A "SYSTEM_REQUIREMENTS.md"
    click B "#the-software-architecture"
    click C "#module-design"
    click D "#module-testing"
    click E "#integration-testing"
    click F "#system-testing"
    click G "#acceptance-testing"

    %% Styling
    classDef requirement fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef design fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef testing fill:#e8f5e8,stroke:#1b5e20,stroke-width:2px

    class A,Z requirement
    class B,C design
    class D,E,F,G testing
```

If the diagram above does not display correctly, [see here](https://github.com/ArduPilot/MethodicConfigurator/blob/master/ARCHITECTURE.md#v-model)
